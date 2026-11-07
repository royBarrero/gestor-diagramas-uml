"""CU07, CU08 y CU09: mientras la voz o la foto esperan a la IA, el servidor sigue atendiendo
a los demás, y lo que se edita durante la espera no se pierde. No usa la base ni OpenAI."""

import asyncio
import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://sin-conexion/pruebas")

from app import realtime
from app.routers import diagramas

PROYECTO_ID = 1
DIAGRAMA_ID = 1
SEGUNDOS_ESPERA = 2


def _clase(nombre: str) -> dict:
    return {
        "id": f"clase-{nombre.lower()}",
        "type": "clase",
        "position": {"x": 0, "y": 0},
        "data": {"nombre": nombre, "atributos": [], "metodos": []},
    }


def _crear_clase(nombre: str) -> dict:
    return {"acciones": [{"accion": "crear_clase", "clase": nombre, "atributos": [], "metodos": []}]}


def _nombres_vivos() -> list[str]:
    return [n["data"]["nombre"] for n in realtime.documentos.obtener(PROYECTO_ID)["nodes"]]


def _edicion_de_otro_integrante(nombre: str) -> dict:
    """El mensaje `cambio_diagrama` de un cliente que agregó una clase."""
    clase = _clase(nombre)
    return {"nodes": [clase], "edges": [], "cambios": {"nodes": [clase["id"]], "edges": []}}


class IaEnEspera:
    """Una llamada a la IA que no termina hasta recibir la señal. Si el servidor está
    bloqueado esperándola, nadie puede dar la señal y se agota el tiempo."""

    def __init__(self, resultado):
        self.resultado = resultado
        self.entro = threading.Event()
        self.senal = threading.Event()
        self.recibio_senal = None

    def __call__(self, *_args, **_kwargs):
        self.entro.set()
        self.recibio_senal = self.senal.wait(SEGUNDOS_ESPERA)
        return self.resultado

    async def esperar_que_entre(self) -> None:
        await asyncio.to_thread(self.entro.wait, SEGUNDOS_ESPERA)


class NoBloqueanTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        realtime.documentos.cerrar(PROYECTO_ID)
        realtime.documentos.abrir(PROYECTO_ID, {"nodes": [_clase("Libro")], "edges": []})
        self.addCleanup(realtime.documentos.cerrar, PROYECTO_ID)

        self.diagrama = SimpleNamespace(id=DIAGRAMA_ID, id_proyecto=PROYECTO_ID, contenido={"nodes": [], "edges": []})
        for parche in (
            patch.object(realtime.sio, "emit", AsyncMock()),
            patch.object(realtime.revisor, "registrar_cambio"),
            patch.object(diagramas, "_obtener_diagrama_o_404", return_value=self.diagrama),
            patch.object(diagramas, "obtener_proyecto_o_404"),
            patch.object(diagramas, "exigir_miembro"),
        ):
            parche.start()
            self.addCleanup(parche.stop)

    def _voz(self, interpretar, transcribir=None, db=None):
        audio = SimpleNamespace(content_type="audio/webm", filename="comando.webm", read=AsyncMock(return_value=b"x"))
        return self._con_ia_de_voz(interpretar, transcribir, audio, db or MagicMock())

    async def _con_ia_de_voz(self, interpretar, transcribir, audio, db):
        with (
            patch.object(diagramas.servicio_voz, "transcribir_audio", transcribir or MagicMock(return_value="texto")),
            patch.object(diagramas.servicio_voz, "interpretar_comando", interpretar),
        ):
            return await diagramas.procesar_comando_voz(DIAGRAMA_ID, audio, SimpleNamespace(id=1), db)

    async def _foto(self, interpretar):
        imagen = SimpleNamespace(content_type="image/png", read=AsyncMock(return_value=b"x"))
        with patch.object(diagramas.servicio_imagen, "interpretar_imagen", interpretar):
            return await diagramas.digitalizar_imagen(DIAGRAMA_ID, imagen, SimpleNamespace(id=1), MagicMock())

    async def _editar_durante_la_espera(self, ia: IaEnEspera, tarea: asyncio.Task, nombre: str) -> None:
        await ia.esperar_que_entre()
        realtime.documentos.aplicar_mensaje(PROYECTO_ID, _edicion_de_otro_integrante(nombre))
        ia.senal.set()
        await tarea

    async def test_la_voz_no_frena_al_servidor_ni_pierde_lo_editado_durante_la_espera(self):
        ia = IaEnEspera(_crear_clase("Prestamo"))
        tarea = asyncio.create_task(self._voz(ia))

        await self._editar_durante_la_espera(ia, tarea, "Autor")

        self.assertTrue(ia.recibio_senal, "El servidor quedó bloqueado esperando a la IA.")
        self.assertEqual(tarea.result().estado, "aplicado")
        self.assertCountEqual(_nombres_vivos(), ["Libro", "Autor", "Prestamo"])

    async def test_la_transcripcion_tampoco_frena_al_servidor(self):
        ia = IaEnEspera("creá la clase prestamo")
        tarea = asyncio.create_task(self._voz(MagicMock(return_value=_crear_clase("Prestamo")), transcribir=ia))

        await self._editar_durante_la_espera(ia, tarea, "Autor")

        self.assertTrue(ia.recibio_senal, "El servidor quedó bloqueado esperando a la IA.")
        self.assertCountEqual(_nombres_vivos(), ["Libro", "Autor", "Prestamo"])

    async def test_dos_comandos_a_la_vez_no_duplican_la_clase(self):
        # Los dos tienen que estar esperando a la IA a la vez para pasar la barrera.
        barrera = threading.Barrier(2, timeout=SEGUNDOS_ESPERA)

        def interpretar(*_args):
            barrera.wait()
            return _crear_clase("Prestamo")

        salidas = await asyncio.gather(self._voz(interpretar), self._voz(interpretar))

        self.assertCountEqual([s.estado for s in salidas], ["aplicado", "no_entendido"])
        rechazo = next(s for s in salidas if s.estado == "no_entendido")
        self.assertIn("Ya existe", rechazo.mensaje)
        self.assertEqual(_nombres_vivos().count("Prestamo"), 1)

    async def test_la_conexion_a_la_base_se_libera_antes_de_esperar_a_la_ia(self):
        db = MagicMock()
        commits_al_llamar = []

        def transcribir(*_args):
            commits_al_llamar.append(db.commit.call_count)
            return "texto"

        await self._voz(MagicMock(return_value=_crear_clase("Prestamo")), transcribir=transcribir, db=db)

        self.assertGreaterEqual(commits_al_llamar[0], 1)

    async def test_la_foto_no_frena_al_servidor_ni_pierde_lo_editado_durante_la_espera(self):
        ia = IaEnEspera(
            {"clases": [{"nombre": "Prestamo", "atributos": [], "metodos": []}], "relaciones": [], "confianza": "alta"}
        )
        tarea = asyncio.create_task(self._foto(ia))

        await self._editar_durante_la_espera(ia, tarea, "Autor")

        self.assertTrue(ia.recibio_senal, "El servidor quedó bloqueado esperando a la IA.")
        self.assertEqual(tarea.result().estado, "aplicado")
        self.assertCountEqual(_nombres_vivos(), ["Libro", "Autor", "Prestamo"])


if __name__ == "__main__":
    unittest.main()
