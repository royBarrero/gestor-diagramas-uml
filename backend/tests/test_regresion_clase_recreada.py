"""Regresión de CU17: crear una clase con el agente, eliminarla y recrearla por voz.

La clase recreada no deja rastro en el chat, cuyo último dato es "Eliminé la clase
Prestamo": el agente tiene que guiarse por el estado actual del diagrama.

No usa la base ni OpenAI, salvo `ModeloRealTest`, que solo corre con PROBAR_IA_REAL=1
porque consume la API. Desde backend/:

    venv\\Scripts\\python -m unittest discover -s tests -t .
"""

import json
import os
import re
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://sin-conexion/pruebas")

from fastapi import HTTPException

from app import realtime
from app.routers import chat, diagramas
from app.services import agente_chat, operaciones_agente

PROYECTO_ID = 1
DIAGRAMA_ID = 1
USUARIO_ID = 1


def _clase_libro() -> dict:
    return {
        "id": "clase-libro",
        "type": "clase",
        "position": {"x": 0, "y": 0},
        "data": {"nombre": "Libro", "atributos": [], "metodos": []},
    }


# Lo que quedó en la base antes de recrear la clase: atrasada respecto de la versión viva.
BASE_ATRASADA = {"nodes": [_clase_libro()], "edges": []}

HISTORIAL_ELIMINADA = [
    {"tipo": "usuario", "autor": "Pepe", "texto": "@ia elimina la clase prestamo"},
    {"tipo": "agente", "autor": None, "texto": "- Eliminé la clase Prestamo."},
]


def _atributo(nombre: str, tipo: str) -> dict:
    return {"nombre": nombre, "tipo": tipo, "visibilidad": "publico"}


def _clase_viva(nombre: str) -> dict | None:
    contenido = realtime.documentos.obtener(PROYECTO_ID)
    return next((n for n in contenido["nodes"] if n["data"]["nombre"] == nombre), None)


class EscenarioBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        realtime.documentos.cerrar(PROYECTO_ID)
        realtime.documentos.abrir(PROYECTO_ID, BASE_ATRASADA)
        realtime.revisor.abrir_proyecto(PROYECTO_ID, BASE_ATRASADA)
        self.addCleanup(realtime.documentos.cerrar, PROYECTO_ID)
        self.addCleanup(realtime.revisor.cerrar_proyecto, PROYECTO_ID)
        self.addCleanup(operaciones_agente._candados.pop, PROYECTO_ID, None)

        self.sio_emit = self._parchar(patch.object(realtime.sio, "emit", AsyncMock()))
        # Sin temporizadores de CU16: acá no interesa el análisis de la clase.
        self._parchar(patch.object(realtime.revisor, "registrar_cambio"))
        self._parchar(patch.object(realtime.historial, "registrar_operacion"))
        self._parchar(patch.object(operaciones_agente, "_leer_diagrama", return_value=(DIAGRAMA_ID, BASE_ATRASADA)))
        self._parchar(patch.object(operaciones_agente, "_es_miembro", return_value=True))
        self._parchar(patch.object(operaciones_agente, "_guardar_aplicacion", return_value=("resumen", None)))
        self._parchar(patch.object(operaciones_agente, "emitir_mensaje", AsyncMock()))
        self.publicar_mensaje = self._parchar(patch.object(operaciones_agente, "publicar_mensaje", AsyncMock()))

    def _parchar(self, parche):
        simulado = parche.start()
        self.addCleanup(parche.stop)
        return simulado

    async def _crear_con_agente(self) -> str:
        crear = {
            "accion": "crear_clase",
            "clase": "Prestamo",
            "atributos": [_atributo("fechaPrestamo", "Date")],
            "metodos": [],
            "cerca_de": None,
        }
        await operaciones_agente.aplicar_operaciones(PROYECTO_ID, [crear], USUARIO_ID)
        return _clase_viva("Prestamo")["id"]

    async def _eliminar_con_agente(self) -> None:
        eliminar = {"accion": "eliminar_clase", "clase": "Prestamo"}
        await operaciones_agente.aplicar_operaciones(PROYECTO_ID, [eliminar], USUARIO_ID)

    async def _recrear_por_voz(self):
        """El endpoint real: solo se simulan el audio y lo que interpreta la IA."""
        interpretado = {
            "acciones": [
                {
                    "accion": "crear_clase",
                    "clase": "Prestamo",
                    "atributos": [_atributo("fechaDevolucion", "Date")],
                    "metodos": [],
                }
            ]
        }
        diagrama = SimpleNamespace(id=DIAGRAMA_ID, id_proyecto=PROYECTO_ID, contenido=BASE_ATRASADA)
        audio = SimpleNamespace(content_type="audio/webm", filename="comando.webm", read=AsyncMock(return_value=b"x"))
        with (
            patch.object(diagramas, "_obtener_diagrama_o_404", return_value=diagrama),
            patch.object(diagramas, "obtener_proyecto_o_404"),
            patch.object(diagramas, "exigir_miembro"),
            patch.object(diagramas.servicio_voz, "transcribir_audio", return_value="creá la clase prestamo"),
            patch.object(diagramas.servicio_voz, "interpretar_comando", return_value=interpretado),
        ):
            return await diagramas.procesar_comando_voz(
                DIAGRAMA_ID, audio, SimpleNamespace(id=USUARIO_ID), MagicMock()
            )

    async def _preparar_clase_recreada(self) -> tuple[str, str]:
        id_viejo = await self._crear_con_agente()
        await self._eliminar_con_agente()
        await self._recrear_por_voz()
        return id_viejo, _clase_viva("Prestamo")["id"]

    def _simular_modelo(self, *, texto: str | None = None, herramienta: tuple[str, dict] | None = None) -> MagicMock:
        """Reemplaza a OpenAI. Devuelve el `create` para ver qué se le mandó."""
        llamadas = None
        if herramienta:
            funcion = SimpleNamespace(name=herramienta[0], arguments=json.dumps(herramienta[1]))
            llamadas = [SimpleNamespace(function=funcion)]
        mensaje = SimpleNamespace(tool_calls=llamadas, content=texto)
        crear = MagicMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=mensaje)]))
        cliente = MagicMock()
        cliente.with_options.return_value.chat.completions.create = crear
        self._parchar(patch.object(agente_chat, "cliente_openai", return_value=cliente))
        return crear

    async def _mencionar(self, texto: str) -> None:
        contexto = {
            "id_autor": USUARIO_ID,
            "autor": "Pepe",
            "texto": texto,
            "proyecto_nombre": "Biblioteca",
            "proyecto_descripcion": None,
            "contenido": BASE_ATRASADA,
            "historial": HISTORIAL_ELIMINADA,
        }
        with patch.object(chat, "_cargar_contexto", return_value=contexto):
            await chat._responder_mencion(PROYECTO_ID, 100, None, None)


class ClaseRecreadaTest(EscenarioBase):
    async def test_la_voz_actualiza_el_documento_vivo_y_emite_el_cambio(self):
        id_viejo = await self._crear_con_agente()
        await self._eliminar_con_agente()
        self.assertIsNone(_clase_viva("Prestamo"))
        self.sio_emit.reset_mock()

        salida = await self._recrear_por_voz()

        self.assertEqual(salida.estado, "aplicado")
        recreada = _clase_viva("Prestamo")
        self.assertIsNotNone(recreada)
        self.assertNotEqual(recreada["id"], id_viejo)
        evento, datos = self.sio_emit.call_args.args
        self.assertEqual(evento, "cambio_diagrama")
        self.assertIn(recreada["id"], datos["cambios"]["nodes"])
        self.assertEqual(self.sio_emit.call_args.kwargs["room"], f"diagrama_{DIAGRAMA_ID}")

    async def test_el_agente_ve_la_clase_despues_del_historial_que_la_da_por_eliminada(self):
        await self._preparar_clase_recreada()
        crear = self._simular_modelo(texto="Sí, la veo.")

        await self._mencionar("@ia ves la clase prestamo?")

        mensajes = crear.call_args.kwargs["messages"]
        contenidos = [m["content"] for m in mensajes]
        indice_historial = next(i for i, c in enumerate(contenidos) if "Eliminé la clase Prestamo" in c)
        indice_estado = next(i for i, c in enumerate(contenidos) if "ESTADO ACTUAL" in c)

        self.assertGreater(indice_estado, indice_historial, "El estado tiene que ir después del historial.")
        self.assertRegex(contenidos[indice_estado], r"Clases que existen ahora:.*Prestamo")
        self.assertIn("- Prestamo", contenidos[indice_estado])
        self.assertEqual(mensajes[-1]["role"], "user")
        self.assertIn("única fuente de verdad", contenidos[0])

    async def test_crear_de_nuevo_se_rechaza_porque_la_validacion_lee_la_misma_version(self):
        await self._preparar_clase_recreada()
        self._simular_modelo(
            herramienta=("crear_clase", {"nombre": "Prestamo", "atributos": [], "metodos": [], "cerca_de": None})
        )

        await self._mencionar("@ia crea la clase prestamo")

        texto = self.publicar_mensaje.call_args.args[2]
        self.assertIn('Ya existe una clase llamada "Prestamo"', texto)

    async def test_un_cambio_del_agente_se_aplica_sobre_la_clase_recreada(self):
        _, id_nuevo = await self._preparar_clase_recreada()
        self._simular_modelo(
            herramienta=(
                "agregar_atributo",
                {"clase": "Prestamo", "nombre": "estado", "tipo": "String", "visibilidad": "publico"},
            )
        )

        await self._mencionar("@ia agregale estado a prestamo")

        prestamo = _clase_viva("Prestamo")
        self.assertEqual(prestamo["id"], id_nuevo)
        self.assertEqual([a["texto"] for a in prestamo["data"]["atributos"]], ["fechaDevolucion", "estado"])


class PedirCorreccionTest(EscenarioBase):
    def setUp(self):
        super().setUp()
        self._parchar(patch.object(chat, "obtener_proyecto_o_404"))
        self._parchar(patch.object(chat, "exigir_miembro"))
        self._parchar(patch.object(chat, "emitir_mensaje", AsyncMock()))
        self._parchar(patch.object(chat.MensajeOut, "desde_modelo", return_value=SimpleNamespace(id=99)))
        self.en_segundo_plano = self._parchar(patch.object(chat.sio, "start_background_task"))

    async def _pedir(self, clase_id: str, db: MagicMock):
        db.get.return_value = SimpleNamespace(
            id_proyecto=PROYECTO_ID,
            tipo="agente",
            elemento_referenciado=clase_id,
            accion=None,
            correcciones=[],
            texto="Pepe, ¿`abuelo` corresponde a Prestamo?",
        )
        return await chat.pedir_correccion(PROYECTO_ID, 83, SimpleNamespace(id=USUARIO_ID), db)

    async def test_una_sugerencia_de_la_clase_eliminada_avisa_con_claridad(self):
        id_viejo, _ = await self._preparar_clase_recreada()
        db = MagicMock()

        with self.assertRaises(HTTPException) as error:
            await self._pedir(id_viejo, db)

        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("se eliminó", error.exception.detail)
        self.assertIn("clase nueva", error.exception.detail)
        db.add.assert_not_called()
        self.en_segundo_plano.assert_not_called()

    async def test_una_sugerencia_de_la_clase_vigente_sigue_y_avisa_que_existe(self):
        _, id_nuevo = await self._preparar_clase_recreada()

        await self._pedir(id_nuevo, MagicMock())

        _, proyecto, mensaje, consulta, sugerencia = self.en_segundo_plano.call_args.args
        self.assertEqual((proyecto, mensaje, sugerencia), (PROYECTO_ID, 99, 83))
        self.assertIn("en la clase Prestamo", consulta)
        self.assertIn("existe en el diagrama actual", consulta)


_NIEGA_LA_CLASE = re.compile(r"no est[aá]|no hay|no existe|eliminada|no se ha vuelto", re.IGNORECASE)


@unittest.skipUnless(os.getenv("PROBAR_IA_REAL") == "1", "Consume la API de OpenAI: se activa con PROBAR_IA_REAL=1.")
class ModeloRealTest(unittest.TestCase):
    """El turno real del incidente. El modelo varía, por eso se repite."""

    def test_el_modelo_no_niega_una_clase_que_figura_en_el_estado_actual(self):
        prestamo = {
            "id": "clase-recreada",
            "type": "clase",
            "position": {"x": 300, "y": 0},
            "data": {
                "nombre": "Prestamo",
                "atributos": [
                    {"id": "a1", "visibilidad": "publico", "tipo": "Date", "texto": "fechaPrestamo"},
                    {"id": "a2", "visibilidad": "publico", "tipo": "Date", "texto": "fechaDevolucion"},
                ],
                "metodos": [],
            },
        }
        contenido = {"nodes": [_clase_libro(), prestamo], "edges": []}
        historial = [
            *HISTORIAL_ELIMINADA,
            {
                "tipo": "agente",
                "autor": None,
                "texto": "La clase Prestamo ya fue eliminada, por lo que no puedo aplicar la corrección sugerida.",
            },
            {"tipo": "usuario", "autor": "Pepe", "texto": "@ia si ya existe deberias verla en la pizarra"},
            {
                "tipo": "agente",
                "autor": None,
                "texto": 'No hay una clase llamada "Prestamo" en el diagrama actual. La clase fue eliminada previamente.',
            },
        ]
        for _ in range(3):
            resultado = agente_chat.interpretar_mencion(
                "Pepe", "@ia ahora ves la clase prestamo en la pizarra??", "Biblioteca", None, contenido, historial
            )
            self.assertEqual(resultado["tipo"], "texto", resultado)
            self.assertNotRegex(resultado["texto"], _NIEGA_LA_CLASE)


if __name__ == "__main__":
    unittest.main()
