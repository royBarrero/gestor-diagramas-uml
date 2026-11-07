"""CU18: registra los cambios del diagrama, vengan de donde vengan.

Las ediciones a mano llegan de a poco: se agrupan por clase y se registran cuando se
suelta o cuando pasa un rato sin cambios. El resto se registra en el momento. Cada clase
tiene como máximo un grupo abierto, de un solo autor: si otro la toca, el grupo se cierra
antes, así un cambio nunca queda a nombre de otra persona.

No se engancha dentro de DocumentosVivos a propósito: `reemplazar` también se usa para
revertir un cambio cuyo guardado falló, y sin nadie conectado no hay documento.

El estado vive en memoria y se toca solo desde el event loop, como en revisor_diagrama.
Un error acá se registra en el log y no corta la edición: el historial es un agregado.
"""

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.historial_cambio import HistorialCambio
from app.schemas.historial_cambio import HistorialOut
from app.services.resumen_cambios import Tramo, entrada_de_lote, entrada_de_tramo, tramos_entre, unir_tramos
from app.services.temporizadores_clase import TemporizadoresPorClase

logger = logging.getLogger(__name__)

ORIGENES_EN_LOTE = ("foto", "importacion")
_PREFIJOS = {"deshacer": "deshizo un cambio del agente: "}


@dataclass
class _Grupo:
    autor: int
    tramo: Tramo


def _sin_propagar(metodo):
    @functools.wraps(metodo)
    def envoltura(*args, **kwargs):
        try:
            return metodo(*args, **kwargs)
        except Exception:
            logger.exception("Error en el historial de cambios (%s)", metodo.__name__)

    return envoltura


def _filas(proyecto_id: int, usuario_id: int, origen: str, por_agente: bool, entradas: list[dict]) -> list:
    return [
        HistorialCambio(id_proyecto=proyecto_id, id_usuario=usuario_id, por_agente=por_agente, origen=origen, **entrada)
        for entrada in entradas
    ]


def _guardar(proyecto_id: int, usuario_id: int, origen: str, por_agente: bool, entradas: list[dict]) -> list[HistorialOut]:
    with SessionLocal() as db:
        filas = _filas(proyecto_id, usuario_id, origen, por_agente, entradas)
        db.add_all(filas)
        db.commit()
        return [HistorialOut.desde_modelo(f) for f in filas]


def registrar_en_sesion(db: Session, proyecto_id: int, usuario_id: int, antes: dict, despues: dict) -> None:
    """Para el autoguardado con el documento cerrado: entra en la misma transacción, y no
    se emite porque no hay nadie conectado. No agrupa: cada guardado ya junta sus cambios."""
    try:
        entradas = [e for e in map(entrada_de_tramo, tramos_entre(antes, despues)) if e]
        db.add_all(_filas(proyecto_id, usuario_id, "manual", False, entradas))
    except Exception:
        logger.exception("No se pudo registrar el autoguardado del proyecto %s", proyecto_id)


class HistorialCambios:
    def __init__(self, publicar: Callable[[HistorialOut], Awaitable[None]]):
        self._publicar = publicar
        self.espera_sin_cambios = 5.0
        self._grupos: dict[tuple[int, str], _Grupo] = {}
        self._temporizadores = TemporizadoresPorClase(self._vencio)
        # Uno por proyecto: los guardados van en orden, y el id coincide con la fecha.
        self._candados: dict[int, asyncio.Lock] = {}
        self._tareas: set[asyncio.Task] = set()

    # ---- Ediciones a mano: se agrupan ----

    @_sin_propagar
    def registrar_edicion(
        self, proyecto_id: int, usuario_id: int, antes: dict | None, despues: dict, propia: str | None = None
    ) -> None:
        """`antes` y `despues` son el documento vivo justo antes y después de este mensaje:
        la diferencia es exactamente lo que hizo este usuario."""
        for tramo in tramos_entre(antes or {}, despues, propia):
            clave = (proyecto_id, tramo.clase_id)
            grupo = self._grupos.get(clave)
            if grupo is not None and grupo.autor != usuario_id:
                self._cerrar(clave)
                grupo = None
            if grupo is None:
                self._grupos[clave] = _Grupo(usuario_id, tramo)
            else:
                grupo.tramo = unir_tramos(grupo.tramo, tramo)
            self._temporizadores.programar((proyecto_id, usuario_id, tramo.clase_id), self.espera_sin_cambios)

    @_sin_propagar
    def registrar_seleccion(self, proyecto_id: int, usuario_id: int, clase_id: str | None) -> None:
        self._temporizadores.soltar(proyecto_id, usuario_id, salvo=clase_id)

    @_sin_propagar
    def usuario_desconectado(self, proyecto_id: int, usuario_id: int) -> None:
        self._temporizadores.soltar(proyecto_id, usuario_id)

    @_sin_propagar
    def cerrar_proyecto(self, proyecto_id: int) -> None:
        self._cerrar_grupos(proyecto_id)

    @_sin_propagar
    def _vencio(self, clave_temporizador: tuple[int, int, str]) -> None:
        proyecto_id, _, clase_id = clave_temporizador
        self._cerrar((proyecto_id, clase_id))

    def _cerrar(self, clave: tuple[int, str]) -> None:
        grupo = self._grupos.pop(clave, None)
        if grupo is None:
            return
        proyecto_id, clase_id = clave
        self._temporizadores.cancelar(lambda c: c == (proyecto_id, grupo.autor, clase_id))
        entrada = entrada_de_tramo(grupo.tramo)
        if entrada is not None:
            self._encolar(proyecto_id, grupo.autor, "manual", False, [entrada])

    def _cerrar_grupos(self, proyecto_id: int, clases: set[str] | None = None) -> None:
        for clave in [c for c in self._grupos if c[0] == proyecto_id and (clases is None or c[1] in clases)]:
            self._cerrar(clave)

    # ---- Operaciones del servidor: se registran en el momento ----

    @_sin_propagar
    def registrar_operacion(
        self, proyecto_id: int, usuario_id: int, origen: str, antes: dict, despues: dict, por_agente: bool = False
    ) -> None:
        if origen in ORIGENES_EN_LOTE:
            self._cerrar_grupos(proyecto_id)
            entradas = [entrada_de_lote(origen, antes, despues)]
        else:
            tramos = tramos_entre(antes, despues)
            self._cerrar_grupos(proyecto_id, {t.clase_id for t in tramos})
            prefijo = _PREFIJOS.get(origen, "")
            entradas = [e for e in (entrada_de_tramo(t, prefijo) for t in tramos) if e]
        if entradas:
            self._encolar(proyecto_id, usuario_id, origen, por_agente, entradas)

    # ---- Guardado y difusión ----

    def _encolar(self, proyecto_id: int, usuario_id: int, origen: str, por_agente: bool, entradas: list[dict]) -> None:
        tarea = asyncio.create_task(self._guardar_y_publicar(proyecto_id, usuario_id, origen, por_agente, entradas))
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    async def _guardar_y_publicar(
        self, proyecto_id: int, usuario_id: int, origen: str, por_agente: bool, entradas: list[dict]
    ) -> None:
        try:
            async with self._candados.setdefault(proyecto_id, asyncio.Lock()):
                salidas = await asyncio.to_thread(_guardar, proyecto_id, usuario_id, origen, por_agente, entradas)
                for salida in salidas:
                    await self._publicar(salida)
        except Exception:
            logger.exception("No se pudo registrar un cambio del proyecto %s", proyecto_id)

    async def esperar_pendientes(self) -> None:
        """Para las pruebas: que termine lo que está guardándose."""
        while self._tareas:
            await asyncio.gather(*self._tareas)
