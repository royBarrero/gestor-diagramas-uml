"""Regresión de CU10: con gente conectada, exportar baja la versión viva del diagrama,
no la de la base, que puede estar atrasada. No usa la base."""

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://sin-conexion/pruebas")

from app import realtime
from app.routers import diagramas

PROYECTO_ID = 1
DIAGRAMA_ID = 1


def _contenido(*nombres: str) -> dict:
    return {
        "nodes": [
            {
                "id": f"clase-{nombre.lower()}",
                "type": "clase",
                "position": {"x": 0, "y": 0},
                "data": {"nombre": nombre, "atributos": [], "metodos": []},
            }
            for nombre in nombres
        ],
        "edges": [],
    }


class ExportacionTest(unittest.TestCase):
    def setUp(self):
        realtime.documentos.cerrar(PROYECTO_ID)
        self.addCleanup(realtime.documentos.cerrar, PROYECTO_ID)
        diagrama = SimpleNamespace(
            id=DIAGRAMA_ID, id_proyecto=PROYECTO_ID, nombre="Biblioteca", contenido=_contenido("EnLaBase")
        )
        for parche in (
            patch.object(diagramas, "_obtener_diagrama_o_404", return_value=diagrama),
            patch.object(diagramas, "obtener_proyecto_o_404"),
            patch.object(diagramas, "exigir_miembro"),
        ):
            parche.start()
            self.addCleanup(parche.stop)

    def _exportar(self, formato: str) -> str:
        respuesta = diagramas.exportar_diagrama(DIAGRAMA_ID, formato, SimpleNamespace(id=1), MagicMock())
        return respuesta.body.decode("utf-8")

    def test_json_exporta_la_version_viva(self):
        realtime.documentos.abrir(PROYECTO_ID, _contenido("EnVivo"))

        exportado = json.loads(self._exportar("json"))

        self.assertEqual([n["data"]["nombre"] for n in exportado["nodes"]], ["EnVivo"])

    def test_xmi_exporta_la_version_viva(self):
        realtime.documentos.abrir(PROYECTO_ID, _contenido("EnVivo"))

        exportado = self._exportar("xmi")

        self.assertIn("EnVivo", exportado)
        self.assertNotIn("EnLaBase", exportado)

    def test_sin_nadie_conectado_exporta_la_base(self):
        self.assertIn("EnLaBase", self._exportar("json"))
        self.assertIn("EnLaBase", self._exportar("xmi"))


if __name__ == "__main__":
    unittest.main()
