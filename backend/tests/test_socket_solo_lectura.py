"""CU19: la app móvil se conecta al socket del proyecto en modo lectura.

Recibe los cambios del diagrama, el chat y el historial, pero no figura como
conectada en la pizarra, no abre el documento vivo ni el revisor, y lo que
mande por el socket se ignora. No usa la base. Desde backend/:

    venv\\Scripts\\python -m unittest tests.test_socket_solo_lectura
"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app import realtime

DIAGRAMA_ID = 9101
PROYECTO_ID = 9102
USUARIO = SimpleNamespace(id=9103, nombre="Lectora")
CONTENIDO = {"nodes": [{"id": "c1", "data": {"nombre": "A"}}], "edges": []}


class SocketSoloLecturaTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sesiones = {}

        async def save_session(sid, sesion):
            self.sesiones[sid] = sesion

        async def get_session(sid):
            return self.sesiones.get(sid)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id=DIAGRAMA_ID, id_proyecto=PROYECTO_ID, contenido=CONTENIDO
        )
        parches = [
            patch.object(realtime, "SessionLocal", return_value=db),
            patch.object(realtime, "obtener_usuario_desde_token", return_value=USUARIO),
            patch.object(realtime, "obtener_proyecto_o_404", return_value=SimpleNamespace(id=PROYECTO_ID)),
            patch.object(realtime, "rol_de_usuario_en_proyecto", return_value="colaborador"),
            patch.object(realtime.sio, "save_session", side_effect=save_session),
            patch.object(realtime.sio, "get_session", side_effect=get_session),
        ]
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        self.enter_room = self._mock(patch.object(realtime.sio, "enter_room", AsyncMock()))
        self.emit = self._mock(patch.object(realtime.sio, "emit", AsyncMock()))
        self.abrir_revisor = self._mock(patch.object(realtime.revisor, "abrir_proyecto"))
        self.registrar_cambio = self._mock(patch.object(realtime.revisor, "registrar_cambio"))
        self.addCleanup(realtime.salas.pop, realtime._room(DIAGRAMA_ID), None)
        self.addCleanup(realtime.documentos.cerrar, PROYECTO_ID)

    def _mock(self, parche):
        mock = parche.start()
        self.addCleanup(parche.stop)
        return mock

    async def _conectar(self, sid, modo):
        query = f"diagramaId={DIAGRAMA_ID}" + (f"&modo={modo}" if modo else "")
        await realtime.connect(sid, {"QUERY_STRING": query}, {"token": "t"})

    async def test_entra_a_las_salas_sin_figurar_como_conectada(self):
        await self._conectar("movil", "lectura")

        rooms = {llamada.args[1] for llamada in self.enter_room.await_args_list}
        self.assertEqual(
            rooms,
            {
                realtime.room_usuario(USUARIO.id),
                realtime._room(DIAGRAMA_ID),
                realtime.room_proyecto(PROYECTO_ID),
            },
        )
        self.assertNotIn("movil", realtime.salas.get(realtime._room(DIAGRAMA_ID), {}))
        self.assertIsNone(realtime.documentos.obtener(PROYECTO_ID))
        self.abrir_revisor.assert_not_called()
        self.emit.assert_not_awaited()  # no se manda la lista de colaboradores

    async def test_lo_que_manda_en_modo_lectura_se_ignora(self):
        await self._conectar("movil", "lectura")

        resultado = await realtime.cambio_diagrama("movil", {"nodes": [], "edges": [], "cambios": {}})
        await realtime.seleccion("movil", {"claseId": "c1"})

        self.assertIsNone(resultado)
        self.emit.assert_not_awaited()
        self.registrar_cambio.assert_not_called()
        self.assertIsNone(realtime.documentos.obtener(PROYECTO_ID))

    async def test_al_desconectarse_no_cierra_la_sala_de_los_editores(self):
        await self._conectar("web", None)
        await self._conectar("movil", "lectura")
        self.emit.reset_mock()

        await realtime.disconnect("movil")

        self.assertIn("web", realtime.salas[realtime._room(DIAGRAMA_ID)])
        self.assertIsNotNone(realtime.documentos.obtener(PROYECTO_ID))
        self.emit.assert_not_awaited()

    async def test_la_web_sigue_conectandose_como_editora(self):
        await self._conectar("web", None)

        self.assertIn("web", realtime.salas[realtime._room(DIAGRAMA_ID)])
        self.abrir_revisor.assert_called_once()


if __name__ == "__main__":
    unittest.main()
