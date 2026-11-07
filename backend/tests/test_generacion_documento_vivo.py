"""Regresión de CU11 y CU12: con gente conectada, se genera código a partir de la versión
viva del diagrama, no de la base, que puede estar atrasada. No usa la base."""

import io
import os
import unittest
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://sin-conexion/pruebas")

from app import realtime
from app.routers import generacion

PROYECTO_ID = 1


def _contenido(nombre: str) -> dict:
    return {
        "nodes": [
            {
                "id": f"clase-{nombre.lower()}",
                "type": "clase",
                "position": {"x": 0, "y": 0},
                "data": {
                    "nombre": nombre,
                    "atributos": [{"id": "a1", "visibilidad": "publico", "tipo": "String", "texto": "titulo"}],
                    "metodos": [],
                },
            }
        ],
        "edges": [],
    }


class GeneracionTest(unittest.TestCase):
    def setUp(self):
        realtime.documentos.cerrar(PROYECTO_ID)
        self.addCleanup(realtime.documentos.cerrar, PROYECTO_ID)

        self.proyecto = SimpleNamespace(
            id=PROYECTO_ID, nombre="Biblioteca", backend_generado_en=datetime.now(timezone.utc)
        )
        for parche in (
            patch.object(generacion, "obtener_proyecto_o_404", return_value=self.proyecto),
            patch.object(generacion, "exigir_administrador"),
        ):
            parche.start()
            self.addCleanup(parche.stop)

        self.db = MagicMock()
        self.db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id_proyecto=PROYECTO_ID, contenido=_contenido("EnLaBase")
        )

    def _archivos(self, generar) -> list[str]:
        respuesta = generar(PROYECTO_ID, SimpleNamespace(id=1), self.db)
        with zipfile.ZipFile(io.BytesIO(respuesta.body)) as archivo_zip:
            return archivo_zip.namelist()

    def _contenido_recibido(self, generar, servicio, funcion: str) -> dict:
        with patch.object(servicio, funcion, return_value=b"zip") as generador:
            generar(PROYECTO_ID, SimpleNamespace(id=1), self.db)
        return generador.call_args.args[0]

    def test_el_backend_incluye_la_clase_que_solo_esta_en_la_version_viva(self):
        realtime.documentos.abrir(PROYECTO_ID, _contenido("EnVivo"))

        archivos = self._archivos(generacion.generar_backend)

        self.assertTrue(any("EnVivo" in nombre for nombre in archivos), archivos)
        self.assertFalse(any("EnLaBase" in nombre for nombre in archivos), archivos)

    def test_el_frontend_parte_de_la_version_viva(self):
        realtime.documentos.abrir(PROYECTO_ID, _contenido("EnVivo"))

        contenido = self._contenido_recibido(
            generacion.generar_frontend, generacion.servicio_frontend, "generar_zip_frontend"
        )

        self.assertEqual(contenido["nodes"][0]["data"]["nombre"], "EnVivo")

    def test_sin_nadie_conectado_se_genera_desde_la_base(self):
        for generar, servicio, funcion in (
            (generacion.generar_backend, generacion.servicio_backend, "generar_zip_backend"),
            (generacion.generar_frontend, generacion.servicio_frontend, "generar_zip_frontend"),
        ):
            contenido = self._contenido_recibido(generar, servicio, funcion)
            self.assertEqual(contenido["nodes"][0]["data"]["nombre"], "EnLaBase")

    def test_sin_diagrama_ni_version_viva_el_contenido_queda_vacio(self):
        self.db.query.return_value.filter.return_value.first.return_value = None

        self.assertEqual(generacion._contenido_diagrama(PROYECTO_ID, self.db), {"nodes": [], "edges": []})


if __name__ == "__main__":
    unittest.main()
