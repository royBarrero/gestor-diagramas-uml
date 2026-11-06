"""CU16: decide cuándo el agente de IA revisa una clase y publica la sugerencia.

Todo el estado vive en memoria del proceso y se toca solo desde el event loop;
la base de datos y OpenAI corren en hilos aparte, sin dejar una sesión abierta
mientras se espera a la IA. Alcanza para el único worker con el que corre el
backend (ver Dockerfile y realtime.py).
"""

import asyncio
import functools
import hashlib
import json
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable

from app.core.database import SessionLocal
from app.core.permisos import rol_de_usuario_en_proyecto
from app.models.mensaje_proyecto import MensajeProyecto
from app.models.proyecto import Proyecto
from app.models.usuario import Usuario
from app.schemas.mensaje_proyecto import MensajeOut
from app.services import agente_sugerencias
from app.services.ia_cliente import ServicioIANoDisponibleError

logger = logging.getLogger(__name__)

SUGERENCIAS_PREVIAS = 10
# Largo de la columna mensajes_proyecto.elemento_referenciado.
MAX_LARGO_ID_CLASE = 100


def _huella(valor) -> str:
    texto = json.dumps(valor, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _items_normalizados(items) -> list:
    """Sin ids ni orden: reordenar una lista o regenerar ids no cambia la clase."""
    if not isinstance(items, list):
        return []
    filas = [
        [i.get("visibilidad"), i.get("tipo"), i.get("texto")]
        for i in items
        if isinstance(i, dict)
    ]
    return sorted(filas, key=str)


def _firma_clase(nodo: dict) -> list:
    """Solo lo que cuenta como cambio: moverla en el lienzo no cambia su firma."""
    data = nodo.get("data") if isinstance(nodo.get("data"), dict) else {}
    return [
        data.get("nombre"),
        _items_normalizados(data.get("atributos")),
        _items_normalizados(data.get("metodos")),
    ]


def _firma_relacion(edge: dict) -> list:
    """Sin el estilo de línea ni el estado de selección, que son solo visuales."""
    data = edge.get("data") if isinstance(edge.get("data"), dict) else {}
    return [
        edge.get("source"),
        edge.get("target"),
        data.get("tipo"),
        data.get("multiplicidadOrigen"),
        data.get("multiplicidadDestino"),
        data.get("nombre"),
        data.get("claseAsociacion"),
    ]


class _Foto:
    """Estado de un diagrama reducido a lo que importa para la revisión."""

    def __init__(self, contenido):
        contenido = contenido if isinstance(contenido, dict) else {}
        nodes = contenido.get("nodes") if isinstance(contenido.get("nodes"), list) else []
        edges = contenido.get("edges") if isinstance(contenido.get("edges"), list) else []
        self.contenido = {
            "nodes": [n for n in nodes if isinstance(n, dict)],
            "edges": [e for e in edges if isinstance(e, dict)],
        }
        self.clases = {
            n["id"]: _firma_clase(n)
            for n in self.contenido["nodes"]
            if isinstance(n.get("id"), str) and len(n["id"]) <= MAX_LARGO_ID_CLASE
        }
        self.relaciones = {
            e["id"]: _firma_relacion(e) for e in self.contenido["edges"] if isinstance(e.get("id"), str)
        }

    def relaciones_de(self, clase_id: str) -> list:
        return sorted((f for f in self.relaciones.values() if clase_id in f[:2]), key=str)

    def huella_de(self, clase_id: str) -> str | None:
        """Huella de la clase con sus relaciones. Las relaciones guardan el id de
        la otra clase, así que renombrar una clase no cambia a sus vecinas."""
        if clase_id not in self.clases:
            return None
        return _huella([self.clases[clase_id], self.relaciones_de(clase_id)])

    def tiene_contenido(self, clase_id: str) -> bool:
        _, atributos, metodos = self.clases[clase_id]
        return bool(atributos or metodos or self.relaciones_de(clase_id))


def _sin_propagar(metodo):
    """Un error de la revisión no puede cortar la colaboración ni un endpoint."""

    @functools.wraps(metodo)
    def envoltura(*args, **kwargs):
        try:
            return metodo(*args, **kwargs)
        except Exception:
            logger.exception("Error en el revisor del diagrama (%s)", metodo.__name__)

    return envoltura


class RevisorDiagrama:
    def __init__(self, publicar: Callable[[MensajeOut], Awaitable[None]]):
        self._publicar = publicar

        self.espera_sin_cambios = 5.0
        self.espera_entre_analisis = 60.0
        self.ventana_limite = 60.0
        self.limite_por_ventana = 10
        # Un mensaje que toca más clases que esto no es una edición a mano
        # (importación, foto): no se analiza.
        self.max_clases_por_cambio = 3

        self._fotos: dict[int, _Foto] = {}
        self._seleccion: dict[int, dict[int, str]] = {}  # proyecto -> {usuario: clase}
        self._silenciados: set[int] = set()
        self._temporizadores: dict[tuple[int, int, str], asyncio.Task] = {}
        self._ultima_huella: dict[tuple[int, str], str] = {}
        self._ultimo_analisis: dict[tuple[int, str], float] = {}
        self._analisis_recientes: dict[int, deque[float]] = {}
        self._tareas: set[asyncio.Task] = set()

    # ---- Eventos que llegan del tiempo real y de los endpoints ----

    @_sin_propagar
    def abrir_proyecto(self, proyecto_id: int, contenido) -> None:
        """Si ya hay gente conectada, su foto está más al día que la base, que se
        guarda con retraso."""
        self._fotos.setdefault(proyecto_id, _Foto(contenido))

    @_sin_propagar
    def cerrar_proyecto(self, proyecto_id: int) -> None:
        self._fotos.pop(proyecto_id, None)
        self._seleccion.pop(proyecto_id, None)

    @_sin_propagar
    def registrar_cambio(self, proyecto_id: int, usuario_id: int, contenido) -> None:
        anterior = self._fotos.get(proyecto_id)
        if anterior is None:
            return
        actual = _Foto(contenido)
        self._fotos[proyecto_id] = actual

        for clase_id in anterior.clases.keys() - actual.clases.keys():
            self._cancelar(lambda clave, c=clase_id: clave[0] == proyecto_id and clave[2] == c)

        cambiadas = self._clases_a_revisar(proyecto_id, usuario_id, anterior, actual)
        if len(cambiadas) > self.max_clases_por_cambio:
            return
        for clase_id in cambiadas:
            self._programar((proyecto_id, usuario_id, clase_id), self.espera_sin_cambios)

    @_sin_propagar
    def registrar_seleccion(self, proyecto_id: int, usuario_id: int, clase_id: str | None) -> None:
        seleccion = self._seleccion.setdefault(proyecto_id, {})
        if clase_id:
            seleccion[usuario_id] = clase_id
        else:
            seleccion.pop(usuario_id, None)
        self._soltar(proyecto_id, usuario_id, salvo=clase_id)

    @_sin_propagar
    def usuario_desconectado(self, proyecto_id: int, usuario_id: int) -> None:
        self._seleccion.get(proyecto_id, {}).pop(usuario_id, None)
        self._soltar(proyecto_id, usuario_id)

    @_sin_propagar
    def cancelar_usuario(self, proyecto_id: int, usuario_id: int) -> None:
        self._seleccion.get(proyecto_id, {}).pop(usuario_id, None)
        self._cancelar(lambda clave: clave[0] == proyecto_id and clave[1] == usuario_id)

    @_sin_propagar
    def silenciar(self, usuario_id: int, activo: bool) -> None:
        if activo:
            self._silenciados.add(usuario_id)
            self._cancelar(lambda clave: clave[1] == usuario_id)
        else:
            self._silenciados.discard(usuario_id)

    # ---- Qué cambió y a quién se le atribuye ----

    def _clases_a_revisar(self, proyecto_id: int, usuario_id: int, anterior: _Foto, actual: _Foto) -> set[str]:
        seleccion = self._seleccion.get(proyecto_id, {})
        propia = seleccion.get(usuario_id)

        objetivos = {
            clase_id for clase_id, firma in actual.clases.items() if anterior.clases.get(clase_id) != firma
        }
        for relacion_id, firma in actual.relaciones.items():
            if anterior.relaciones.get(relacion_id) == firma:
                continue
            origen, destino = firma[:2]
            # Una sola clase por relación, para no pagar dos consultas ni
            # recibir dos sugerencias iguales.
            objetivo = propia if propia in (origen, destino) else origen
            if objetivo in actual.clases:
                objetivos.add(objetivo)

        # El diagrama viaja completo: un mensaje con datos un poco viejos puede
        # parecer un cambio en la clase que está editando otra persona.
        ajenas = {clase for usuario, clase in seleccion.items() if usuario != usuario_id}
        return {c for c in objetivos if c not in ajenas or c == propia}

    # ---- Temporizadores ----

    def _programar(self, clave: tuple[int, int, str], espera: float) -> None:
        pendiente = self._temporizadores.get(clave)
        if pendiente:
            pendiente.cancel()
        self._temporizadores[clave] = asyncio.create_task(self._esperar(clave, espera))

    async def _esperar(self, clave: tuple[int, int, str], espera: float) -> None:
        await asyncio.sleep(espera)
        del self._temporizadores[clave]
        self._intentar_analisis(clave)

    def _cancelar(self, coincide: Callable[..., bool]) -> None:
        for clave in [c for c in self._temporizadores if coincide(c)]:
            self._temporizadores.pop(clave).cancel()

    def _soltar(self, proyecto_id: int, usuario_id: int, salvo: str | None = None) -> None:
        for clave in [
            c for c in self._temporizadores if c[0] == proyecto_id and c[1] == usuario_id and c[2] != salvo
        ]:
            self._temporizadores.pop(clave).cancel()
            self._intentar_analisis(clave)

    # ---- Análisis ----

    def _tiempo_hasta_poder_analizar(self, proyecto_id: int, clase_id: str, ahora: float) -> float:
        espera = 0.0
        ultimo = self._ultimo_analisis.get((proyecto_id, clase_id))
        if ultimo is not None:
            espera = self.espera_entre_analisis - (ahora - ultimo)

        recientes = self._analisis_recientes.setdefault(proyecto_id, deque())
        while recientes and ahora - recientes[0] >= self.ventana_limite:
            recientes.popleft()
        if len(recientes) >= self.limite_por_ventana:
            espera = max(espera, self.ventana_limite - (ahora - recientes[0]))
        return espera

    @_sin_propagar
    def _intentar_analisis(self, clave: tuple[int, int, str]) -> None:
        proyecto_id, usuario_id, clase_id = clave
        foto = self._fotos.get(proyecto_id)
        if foto is None or usuario_id in self._silenciados:
            return
        huella = foto.huella_de(clase_id)
        if huella is None or not foto.tiene_contenido(clase_id):
            return
        if huella == self._ultima_huella.get((proyecto_id, clase_id)):
            return

        ahora = time.monotonic()
        espera = self._tiempo_hasta_poder_analizar(proyecto_id, clase_id, ahora)
        if espera > 0:
            self._programar(clave, espera)
            return

        self._ultimo_analisis[(proyecto_id, clase_id)] = ahora
        self._analisis_recientes[proyecto_id].append(ahora)
        tarea = asyncio.create_task(self._analizar(clave, huella, foto.contenido))
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    async def _analizar(self, clave: tuple[int, int, str], huella: str, contenido: dict) -> None:
        proyecto_id, usuario_id, clase_id = clave
        try:
            contexto = await asyncio.to_thread(_cargar_contexto, proyecto_id, usuario_id, clase_id)
            if contexto is None:
                return

            resultado = await asyncio.to_thread(
                agente_sugerencias.analizar_clase,
                contexto["destinatario"],
                contexto["proyecto_nombre"],
                contexto["proyecto_descripcion"],
                clase_id,
                contenido,
                contexto["sugerencias_previas"],
            )
            self._ultima_huella[(proyecto_id, clase_id)] = huella

            mensaje = (resultado.get("mensaje") or "").strip()
            if not resultado.get("hay_problema") or not mensaje:
                return
            if self._respuesta_vieja(proyecto_id, clase_id, huella) or usuario_id in self._silenciados:
                return

            salida = await asyncio.to_thread(_guardar_sugerencia, proyecto_id, usuario_id, clase_id, mensaje)
            if salida is not None:
                await self._publicar(salida)
        except ServicioIANoDisponibleError as exc:
            logger.warning("Análisis de la clase %s omitido: %s", clase_id, exc)
        except Exception:
            logger.exception("Error al analizar la clase %s", clase_id)

    def _respuesta_vieja(self, proyecto_id: int, clase_id: str, huella: str) -> bool:
        foto = self._fotos.get(proyecto_id)
        # Sin foto ya no queda nadie editando, así que la clase no pudo cambiar.
        return foto is not None and foto.huella_de(clase_id) != huella


def _es_miembro(proyecto: Proyecto | None, usuario: Usuario | None, db) -> bool:
    return bool(proyecto and usuario and rol_de_usuario_en_proyecto(proyecto, usuario, db))


def _cargar_contexto(proyecto_id: int, usuario_id: int, clase_id: str) -> dict | None:
    """None si el usuario ya no es miembro o el proyecto ya no existe."""
    with SessionLocal() as db:
        proyecto = db.get(Proyecto, proyecto_id)
        usuario = db.get(Usuario, usuario_id)
        if not _es_miembro(proyecto, usuario, db):
            return None
        previas = (
            db.query(MensajeProyecto.texto)
            .filter(
                MensajeProyecto.id_proyecto == proyecto_id,
                MensajeProyecto.tipo == "agente",
                MensajeProyecto.elemento_referenciado == clase_id,
            )
            .order_by(MensajeProyecto.id.desc())
            .limit(SUGERENCIAS_PREVIAS)
            .all()
        )
        return {
            "destinatario": usuario.nombre,
            "proyecto_nombre": proyecto.nombre,
            "proyecto_descripcion": proyecto.descripcion,
            "sugerencias_previas": [fila.texto for fila in reversed(previas)],
        }


def _guardar_sugerencia(proyecto_id: int, usuario_id: int, clase_id: str, texto: str) -> MensajeOut | None:
    """Vuelve a comprobar la membresía: pudieron quitarlo mientras la IA respondía."""
    with SessionLocal() as db:
        if not _es_miembro(db.get(Proyecto, proyecto_id), db.get(Usuario, usuario_id), db):
            return None
        mensaje = MensajeProyecto(
            id_proyecto=proyecto_id,
            tipo="agente",
            texto=texto,
            id_usuario_destino=usuario_id,
            elemento_referenciado=clase_id,
        )
        db.add(mensaje)
        db.commit()
        db.refresh(mensaje)
        return MensajeOut.desde_modelo(mensaje)
