"""CU18: cuándo se registra cada cambio y a nombre de quién. No usa la base ni OpenAI."""

import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://sin-conexion/pruebas")

from app import realtime
from app.routers import diagramas
from app.services import historial_cambios, operaciones_agente
from app.services.revisor_diagrama import RevisorDiagrama

PROYECTO_ID = 1
DIAGRAMA_ID = 1
ANA, BETO = 1, 2
ESPERA = 0.03


def _clase(nombre="Cliente", atributos=()) -> dict:
    return {
        "id": f"c-{nombre.lower()}",
        "type": "clase",
        "position": {"x": 0, "y": 0},
        "data": {
            "nombre": nombre,
            "atributos": [
                {"id": f"a-{a}", "texto": a, "tipo": "String", "visibilidad": "publico"} for a in atributos
            ],
            "metodos": [],
        },
    }


def _diagrama(*nodos) -> dict:
    return {"nodes": list(nodos), "edges": []}


class ConGuardadoSimulado(unittest.IsolatedAsyncioTestCase):
    """Reemplaza el guardado en la base: deja anotado lo que se habría guardado."""

    def setUp(self):
        self.guardadas = []

        def guardar(proyecto_id, usuario_id, origen, por_agente, entradas):
            filas = [
                SimpleNamespace(
                    id_proyecto=proyecto_id,
                    autor=usuario_id,
                    origen=origen,
                    por_agente=por_agente,
                    model_dump=lambda mode: {},
                    **entrada,
                )
                for entrada in entradas
            ]
            self.guardadas.extend(filas)
            return filas

        self.guardar = guardar
        parche = patch.object(historial_cambios, "_guardar", side_effect=guardar)
        self.guardar_simulado = parche.start()
        self.addCleanup(parche.stop)


class AgrupacionTest(ConGuardadoSimulado):
    def setUp(self):
        super().setUp()
        self.publicar = AsyncMock()
        self.historial = historial_cambios.HistorialCambios(publicar=self.publicar)
        self.historial.espera_sin_cambios = 60  # Solo vence si la prueba lo pide.

    async def _pendientes(self):
        await self.historial.esperar_pendientes()

    def _editar(self, usuario, antes, despues):
        self.historial.registrar_edicion(PROYECTO_ID, usuario, antes, despues)

    async def test_varios_cambios_seguidos_son_una_sola_entrada(self):
        self.historial.espera_sin_cambios = ESPERA
        self._editar(ANA, _diagrama(_clase()), _diagrama(_clase(atributos=["e"])))
        self._editar(ANA, _diagrama(_clase(atributos=["e"])), _diagrama(_clase(atributos=["e", "f"])))
        self._editar(ANA, _diagrama(_clase(atributos=["e", "f"])), _diagrama(_clase(atributos=["e", "f", "g"])))
        self.assertEqual(self.guardadas, [], "No se registra nada mientras sigue editando.")

        await asyncio.sleep(ESPERA * 3)
        await self._pendientes()

        self.assertEqual(len(self.guardadas), 1)
        self.assertEqual(self.guardadas[0].resumen, "agregó los atributos e, f y g a Cliente")
        self.assertEqual((self.guardadas[0].autor, self.guardadas[0].origen), (ANA, "manual"))

    async def test_cada_cambio_reinicia_la_espera(self):
        self.historial.espera_sin_cambios = ESPERA * 3
        self._editar(ANA, _diagrama(_clase()), _diagrama(_clase(atributos=["e"])))
        await asyncio.sleep(ESPERA * 2)
        self._editar(ANA, _diagrama(_clase(atributos=["e"])), _diagrama(_clase(atributos=["e", "f"])))
        await asyncio.sleep(ESPERA * 2)
        self.assertEqual(self.guardadas, [])

    async def test_soltar_la_clase_registra_al_instante(self):
        self._editar(ANA, _diagrama(_clase()), _diagrama(_clase(atributos=["e"])))

        self.historial.registrar_seleccion(PROYECTO_ID, ANA, "otra-clase")
        await self._pendientes()

        self.assertEqual(len(self.guardadas), 1)

    async def test_seguir_en_la_misma_clase_no_registra(self):
        self._editar(ANA, _diagrama(_clase()), _diagrama(_clase(atributos=["e"])))

        self.historial.registrar_seleccion(PROYECTO_ID, ANA, "c-cliente")
        await self._pendientes()

        self.assertEqual(self.guardadas, [])

    async def test_soltar_una_clase_no_afecta_a_otro_usuario(self):
        self._editar(ANA, _diagrama(_clase()), _diagrama(_clase(atributos=["e"])))

        self.historial.registrar_seleccion(PROYECTO_ID, BETO, None)
        await self._pendientes()

        self.assertEqual(self.guardadas, [])

    async def test_desconectarse_registra(self):
        self._editar(ANA, _diagrama(_clase()), _diagrama(_clase(atributos=["e"])))

        self.historial.usuario_desconectado(PROYECTO_ID, ANA)
        await self._pendientes()

        self.assertEqual(len(self.guardadas), 1)

    async def test_cerrar_el_proyecto_registra_lo_abierto(self):
        self._editar(ANA, _diagrama(_clase()), _diagrama(_clase(atributos=["e"])))

        self.historial.cerrar_proyecto(PROYECTO_ID)
        await self._pendientes()

        self.assertEqual(len(self.guardadas), 1)

    async def test_dos_usuarios_alternados_quedan_cada_uno_con_lo_suyo(self):
        self._editar(ANA, _diagrama(_clase()), _diagrama(_clase(atributos=["a"])))
        self._editar(BETO, _diagrama(_clase(atributos=["a"])), _diagrama(_clase(atributos=["a", "b"])))
        self._editar(ANA, _diagrama(_clase(atributos=["a", "b"])), _diagrama(_clase(atributos=["a", "b", "c"])))
        self.historial.cerrar_proyecto(PROYECTO_ID)
        await self._pendientes()

        self.assertEqual(
            [(e.autor, e.resumen) for e in self.guardadas],
            [
                (ANA, "agregó el atributo a a Cliente"),
                (BETO, "agregó el atributo b a Cliente"),
                (ANA, "agregó el atributo c a Cliente"),
            ],
        )

    async def test_mover_una_clase_no_registra_ni_programa_nada(self):
        movida = _clase()
        movida["position"] = {"x": 900, "y": 900}

        self._editar(ANA, _diagrama(_clase()), _diagrama(movida))
        self.historial.usuario_desconectado(PROYECTO_ID, ANA)
        await self._pendientes()

        self.assertEqual(self.guardadas, [])

    async def test_clases_distintas_son_entradas_distintas(self):
        antes = _diagrama(_clase(), _clase("Venta"))
        despues = _diagrama(_clase(atributos=["a"]), _clase("Venta", atributos=["b"]))

        self._editar(ANA, antes, despues)
        self.historial.cerrar_proyecto(PROYECTO_ID)
        await self._pendientes()

        self.assertCountEqual([e.nombre_elemento for e in self.guardadas], ["Cliente", "Venta"])

    async def test_una_operacion_cierra_el_grupo_abierto_de_esa_clase_antes(self):
        self._editar(ANA, _diagrama(_clase()), _diagrama(_clase(atributos=["a"])))

        self.historial.registrar_operacion(
            PROYECTO_ID, BETO, "voz", _diagrama(_clase(atributos=["a"])), _diagrama(_clase(atributos=["a", "b"]))
        )
        await self._pendientes()

        self.assertEqual([(e.autor, e.origen) for e in self.guardadas], [(ANA, "manual"), (BETO, "voz")])

    async def test_cada_entrada_se_publica(self):
        self.historial.registrar_operacion(PROYECTO_ID, ANA, "voz", _diagrama(), _diagrama(_clase()))
        await self._pendientes()

        self.publicar.assert_awaited_once_with(self.guardadas[0])

    async def test_un_error_al_guardar_no_corta_nada(self):
        self.guardar_simulado.side_effect = RuntimeError("la base se cayó")

        with self.assertLogs("app.services.historial_cambios", level="ERROR"):
            self.historial.registrar_operacion(PROYECTO_ID, ANA, "voz", _diagrama(), _diagrama(_clase()))
            await self._pendientes()

        self.publicar.assert_not_awaited()

    async def test_un_contenido_que_rompe_la_comparacion_no_corta_la_edicion(self):
        with patch.object(historial_cambios, "tramos_entre", side_effect=RuntimeError("inesperado")):
            with self.assertLogs("app.services.historial_cambios", level="ERROR"):
                self.historial.registrar_edicion(PROYECTO_ID, ANA, _diagrama(), _diagrama())


class OrigenesTest(ConGuardadoSimulado):
    """Cada origen, por su camino real."""

    def setUp(self):
        super().setUp()
        realtime.documentos.cerrar(PROYECTO_ID)
        realtime.documentos.abrir(PROYECTO_ID, _diagrama(_clase("Libro")))
        realtime.revisor.abrir_proyecto(PROYECTO_ID, _diagrama(_clase("Libro")))
        self.addCleanup(realtime.documentos.cerrar, PROYECTO_ID)
        self.addCleanup(realtime.revisor.cerrar_proyecto, PROYECTO_ID)
        self.addCleanup(operaciones_agente._candados.pop, PROYECTO_ID, None)

        self.emitir = AsyncMock()
        self.diagrama = SimpleNamespace(
            id=DIAGRAMA_ID, id_proyecto=PROYECTO_ID, nombre="Biblioteca", contenido=_diagrama(_clase("Libro"))
        )
        self.guardar_aplicacion = MagicMock(return_value=("resumen", None))
        for parche in (
            patch.object(realtime.sio, "emit", self.emitir),
            patch.object(realtime.revisor, "registrar_cambio"),
            patch.object(diagramas, "_obtener_diagrama_o_404", return_value=self.diagrama),
            patch.object(diagramas, "obtener_proyecto_o_404"),
            patch.object(diagramas, "exigir_miembro"),
            patch.object(operaciones_agente, "_leer_diagrama", return_value=(DIAGRAMA_ID, self.diagrama.contenido)),
            patch.object(operaciones_agente, "_es_miembro", return_value=True),
            patch.object(operaciones_agente, "_guardar_aplicacion", self.guardar_aplicacion),
            patch.object(operaciones_agente, "emitir_mensaje", AsyncMock()),
            patch.object(operaciones_agente, "emitir_mensaje_actualizado", AsyncMock()),
        ):
            parche.start()
            self.addCleanup(parche.stop)

    async def _pendientes(self):
        await realtime.historial.esperar_pendientes()

    async def _agente_crea(self, nombre="Prestamo"):
        crear = {"accion": "crear_clase", "clase": nombre, "atributos": [], "metodos": [], "cerca_de": None}
        await operaciones_agente.aplicar_operaciones(PROYECTO_ID, [crear], BETO)

    async def test_voz(self):
        interpretado = {"acciones": [{"accion": "crear_clase", "clase": "Prestamo", "atributos": [], "metodos": []}]}
        audio = SimpleNamespace(content_type="audio/webm", filename="a.webm", read=AsyncMock(return_value=b"x"))
        with (
            patch.object(diagramas.servicio_voz, "transcribir_audio", return_value="texto"),
            patch.object(diagramas.servicio_voz, "interpretar_comando", return_value=interpretado),
        ):
            await diagramas.procesar_comando_voz(DIAGRAMA_ID, audio, SimpleNamespace(id=ANA), MagicMock())
        await self._pendientes()

        entrada = self.guardadas[0]
        self.assertEqual((entrada.origen, entrada.autor, entrada.por_agente), ("voz", ANA, False))
        self.assertEqual(entrada.resumen, "creó la clase Prestamo")

    async def test_voz_sin_nadie_conectado_igual_queda_registrada(self):
        realtime.documentos.cerrar(PROYECTO_ID)
        interpretado = {"acciones": [{"accion": "crear_clase", "clase": "Prestamo", "atributos": [], "metodos": []}]}
        audio = SimpleNamespace(content_type="audio/webm", filename="a.webm", read=AsyncMock(return_value=b"x"))
        with (
            patch.object(diagramas.servicio_voz, "transcribir_audio", return_value="texto"),
            patch.object(diagramas.servicio_voz, "interpretar_comando", return_value=interpretado),
        ):
            await diagramas.procesar_comando_voz(DIAGRAMA_ID, audio, SimpleNamespace(id=ANA), MagicMock())
        await self._pendientes()

        self.assertEqual([e.resumen for e in self.guardadas], ["creó la clase Prestamo"])

    async def test_foto_es_una_sola_entrada(self):
        resultado = {
            "clases": [{"nombre": "A", "atributos": [], "metodos": []}, {"nombre": "B", "atributos": [], "metodos": []}],
            "relaciones": [],
            "confianza": "alta",
        }
        imagen = SimpleNamespace(content_type="image/png", read=AsyncMock(return_value=b"x"))
        with patch.object(diagramas.servicio_imagen, "interpretar_imagen", return_value=resultado):
            await diagramas.digitalizar_imagen(DIAGRAMA_ID, imagen, SimpleNamespace(id=ANA), MagicMock())
        await self._pendientes()

        self.assertEqual(
            [(e.origen, e.resumen) for e in self.guardadas], [("foto", "digitalizó por foto 2 clases y 0 relaciones")]
        )

    async def test_importacion_es_una_sola_entrada(self):
        archivo = SimpleNamespace(read=AsyncMock(return_value=b"x"))
        importado = _diagrama(_clase("A"), _clase("B"), _clase("C"))
        with patch.object(diagramas.servicio_exportacion, "contenido_desde_json", return_value=importado):
            await diagramas.importar_diagrama(DIAGRAMA_ID, "json", archivo, SimpleNamespace(id=ANA), MagicMock())
        await self._pendientes()

        self.assertEqual(
            [(e.origen, e.resumen) for e in self.guardadas], [("importacion", "importó 3 clases y 0 relaciones")]
        )

    async def test_agente_queda_a_nombre_de_quien_lo_pidio(self):
        await self._agente_crea()
        await self._pendientes()

        entrada = self.guardadas[0]
        self.assertEqual((entrada.origen, entrada.autor, entrada.por_agente), ("agente", BETO, True))
        self.assertEqual(entrada.resumen, "creó la clase Prestamo")

    async def test_si_el_agente_no_pudo_guardar_no_se_registra_nada(self):
        self.guardar_aplicacion.side_effect = RuntimeError("la base se cayó")

        with self.assertRaises(RuntimeError):
            await self._agente_crea()
        await self._pendientes()

        self.assertEqual(self.guardadas, [])
        self.assertEqual([n["data"]["nombre"] for n in realtime.documentos.obtener(PROYECTO_ID)["nodes"]], ["Libro"])

    async def test_deshacer(self):
        antes = realtime.documentos.obtener(PROYECTO_ID)
        await self._agente_crea()
        await self._pendientes()
        self.guardadas.clear()
        accion = {
            "estado": "aplicada",
            "id_solicitante": BETO,
            "copia_contenido": antes,
            "huella_resultante": operaciones_agente.huella_sin_posiciones(realtime.documentos.obtener(PROYECTO_ID)),
        }
        with (
            patch.object(operaciones_agente, "_leer_accion", return_value=accion),
            patch.object(operaciones_agente, "_guardar_deshacer", return_value=("aviso", "mensaje", None)),
            patch.object(operaciones_agente, "emitir_mensaje", AsyncMock()),
        ):
            await operaciones_agente.deshacer(PROYECTO_ID, 1, BETO, "Beto")
        await self._pendientes()

        entrada = self.guardadas[0]
        self.assertEqual((entrada.origen, entrada.autor, entrada.por_agente), ("deshacer", BETO, False))
        self.assertEqual(entrada.resumen, "deshizo un cambio del agente: eliminó la clase Prestamo")

    async def test_edicion_a_mano_por_el_socket(self):
        realtime.historial.espera_sin_cambios = 60
        self.addCleanup(setattr, realtime.historial, "espera_sin_cambios", 5.0)
        room = f"diagrama_{DIAGRAMA_ID}"
        realtime.salas[room] = {"sid-1": {"id": ANA, "nombre": "Ana", "claseId": None}}
        self.addCleanup(realtime.salas.pop, room, None)
        sesion = {"room": room, "proyecto_id": PROYECTO_ID, "usuario_id": ANA, "nombre": "Ana"}
        nueva = _clase("Prestamo")

        with patch.object(realtime.sio, "get_session", AsyncMock(return_value=sesion)):
            await realtime.cambio_diagrama(
                "sid-1", {"nodes": [nueva], "edges": [], "cambios": {"nodes": [nueva["id"]], "edges": []}}
            )
            self.assertEqual(self.guardadas, [], "A mano se agrupa: todavía no se registra.")
            await realtime.seleccion("sid-1", {"claseId": None})
        await self._pendientes()

        self.assertEqual([(e.origen, e.autor, e.resumen) for e in self.guardadas], [("manual", ANA, "creó la clase Prestamo")])

    def test_autoguardado_con_el_documento_cerrado_entra_en_la_misma_transaccion(self):
        realtime.documentos.cerrar(PROYECTO_ID)
        db = MagicMock()

        diagramas.actualizar_diagrama(
            DIAGRAMA_ID,
            SimpleNamespace(contenido=_diagrama(_clase("Libro"), _clase("Prestamo"))),
            SimpleNamespace(id=ANA),
            db,
        )

        filas = db.add_all.call_args.args[0]
        self.assertEqual([(f.origen, f.id_usuario, f.resumen) for f in filas], [("manual", ANA, "creó la clase Prestamo")])
        self.assertLess(
            [c[0] for c in db.method_calls].index("add_all"), [c[0] for c in db.method_calls].index("commit")
        )

    def test_autoguardado_con_el_documento_abierto_no_registra_de_nuevo(self):
        db = MagicMock()

        diagramas.actualizar_diagrama(
            DIAGRAMA_ID, SimpleNamespace(contenido=_diagrama(_clase("Otra"))), SimpleNamespace(id=ANA), db
        )

        db.add_all.assert_not_called()


class EmisionTest(unittest.IsolatedAsyncioTestCase):
    async def test_va_a_la_sala_del_proyecto(self):
        entrada = SimpleNamespace(id_proyecto=7, model_dump=lambda mode: {"id": 1})
        with patch.object(realtime.sio, "emit", AsyncMock()) as emitir:
            await realtime.emitir_historial(entrada)

        emitir.assert_awaited_once_with("historial_cambio", {"id": 1}, room="proyecto_7")


class RevisorSigueIgualTest(unittest.IsolatedAsyncioTestCase):
    """CU16 pasó a usar los temporizadores compartidos: se comporta igual."""

    def setUp(self):
        self.revisor = RevisorDiagrama(publicar=AsyncMock())
        self.revisor.espera_sin_cambios = 0.03
        self.revisor.abrir_proyecto(PROYECTO_ID, _diagrama(_clase()))

    async def test_analiza_al_pasar_la_espera(self):
        with patch.object(self.revisor._temporizadores, "_al_vencer") as analizar:
            self.revisor.registrar_cambio(PROYECTO_ID, ANA, _diagrama(_clase(atributos=["a"])))
            analizar.assert_not_called()
            await asyncio.sleep(0.1)

        analizar.assert_called_once_with((PROYECTO_ID, ANA, "c-cliente"))

    async def test_analiza_al_soltar_la_clase(self):
        with patch.object(self.revisor._temporizadores, "_al_vencer") as analizar:
            self.revisor.registrar_cambio(PROYECTO_ID, ANA, _diagrama(_clase(atributos=["a"])))
            self.revisor.registrar_seleccion(PROYECTO_ID, ANA, None)

        analizar.assert_called_once_with((PROYECTO_ID, ANA, "c-cliente"))

    async def test_eliminar_la_clase_cancela_el_analisis(self):
        with patch.object(self.revisor._temporizadores, "_al_vencer") as analizar:
            self.revisor.registrar_cambio(PROYECTO_ID, ANA, _diagrama(_clase(atributos=["a"])))
            self.revisor.registrar_cambio(PROYECTO_ID, ANA, _diagrama())
            await asyncio.sleep(0.1)

        analizar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
