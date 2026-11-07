"""CU18: los endpoints del historial contra PostgreSQL de verdad, porque el filtro por
clase usa JSONB. Todo pasa en una transacción que se descarta: no deja nada en la base.

Necesita la tabla creada (`python create_tables.py`) y la base de backend/.env. Se corre
sola, porque las demás pruebas apuntan a una base inexistente. Desde backend/:

    set PROBAR_BD_REAL=1
    venv\\Scripts\\python -m unittest tests.test_historial_endpoint
"""

import os
import unittest

from fastapi import HTTPException

PROBAR = os.getenv("PROBAR_BD_REAL") == "1"


@unittest.skipUnless(PROBAR, "Usa la base real: se activa con PROBAR_BD_REAL=1.")
class HistorialEndpointTest(unittest.TestCase):
    def setUp(self):
        from app.core.database import SessionLocal
        from app.models.historial_cambio import HistorialCambio
        from app.models.miembro_proyecto import MiembroProyecto
        from app.models.proyecto import Proyecto
        from app.models.usuario import Usuario

        self.db = SessionLocal()
        self.addCleanup(self.db.close)
        self.addCleanup(self.db.rollback)

        def usuario(nombre):
            fila = Usuario(nombre=nombre, email=f"{nombre}-prueba-cu18@example.invalid", password_hash="x")
            self.db.add(fila)
            self.db.flush()
            return fila

        self.ana, self.beto, self.ajeno = usuario("Ana"), usuario("Beto"), usuario("Ajeno")
        self.proyecto = Proyecto(nombre="Prueba CU18", id_usuario_creador=self.ana.id)
        self.db.add(self.proyecto)
        self.db.flush()
        self.db.add(MiembroProyecto(id_proyecto=self.proyecto.id, id_usuario=self.ana.id, rol="administrador"))
        self.db.add(MiembroProyecto(id_proyecto=self.proyecto.id, id_usuario=self.beto.id, rol="colaborador"))

        def entrada(autor, elemento, nombre, ids_clases, resumen, por_agente=False):
            fila = HistorialCambio(
                id_proyecto=self.proyecto.id,
                id_usuario=autor.id,
                por_agente=por_agente,
                origen="agente" if por_agente else "manual",
                tipo_operacion="editar_clase",
                id_elemento=elemento,
                nombre_elemento=nombre,
                detalle={"ids_clases": ids_clases},
                resumen=resumen,
            )
            self.db.add(fila)
            self.db.flush()
            return fila

        self.e1 = entrada(self.ana, "c1", "Cliente", ["c1"], "creó la clase Cliente")
        self.e2 = entrada(self.beto, "c2", "Venta", ["c2"], "creó la clase Venta", por_agente=True)
        self.e3 = entrada(self.ana, "c1", "Comprador", ["c1", "c2"], "creó una asociación")
        self.e4 = entrada(self.beto, None, None, ["c9"], "importó 1 clase y 0 relaciones")

    def _listar(self, usuario=None, **filtros):
        from app.routers.historial import listar_historial

        parametros = {"usuario_id": None, "clase_id": None, "antes_de": None, "limite": 50, **filtros}
        return listar_historial(self.proyecto.id, usuario_actual=usuario or self.ana, db=self.db, **parametros)

    def test_del_mas_reciente_al_mas_antiguo(self):
        self.assertEqual([e.id for e in self._listar()], [self.e4.id, self.e3.id, self.e2.id, self.e1.id])

    def test_paginado(self):
        primera = self._listar(limite=2)
        segunda = self._listar(limite=2, antes_de=primera[-1].id)
        self.assertEqual([e.id for e in primera + segunda], [self.e4.id, self.e3.id, self.e2.id, self.e1.id])

    def test_filtro_por_usuario(self):
        self.assertEqual([e.id for e in self._listar(usuario_id=self.beto.id)], [self.e4.id, self.e2.id])

    def test_filtro_por_clase_incluye_las_relaciones_registradas_en_la_otra_clase(self):
        self.assertEqual([e.id for e in self._listar(clase_id="c2")], [self.e3.id, self.e2.id])

    def test_trae_todo_lo_necesario_para_mostrar_la_entrada(self):
        salida = next(e for e in self._listar() if e.id == self.e2.id)
        self.assertEqual(salida.autor_nombre, "Beto")
        self.assertTrue(salida.autor_color.startswith("#"))
        self.assertTrue(salida.por_agente)
        self.assertEqual(salida.resumen, "creó la clase Venta")
        self.assertIsNotNone(salida.created_at)

    def test_quien_no_es_miembro_no_puede_verlo(self):
        with self.assertRaises(HTTPException) as error:
            self._listar(usuario=self.ajeno)
        self.assertEqual(error.exception.status_code, 403)

    def test_filtros_traen_integrantes_y_el_ultimo_nombre_de_cada_clase(self):
        from app.routers.historial import filtros_historial

        filtros = filtros_historial(self.proyecto.id, usuario_actual=self.ana, db=self.db)

        self.assertEqual([i.nombre for i in filtros.integrantes], ["Ana", "Beto"])
        self.assertEqual({c.id: c.nombre for c in filtros.clases}, {"c1": "Comprador", "c2": "Venta"})

    def test_filtros_rechazan_a_quien_no_es_miembro(self):
        from app.routers.historial import filtros_historial

        with self.assertRaises(HTTPException) as error:
            filtros_historial(self.proyecto.id, usuario_actual=self.ajeno, db=self.db)
        self.assertEqual(error.exception.status_code, 403)

    def test_eliminar_el_proyecto_se_lleva_su_historial(self):
        from app.models.historial_cambio import HistorialCambio

        id_proyecto = self.proyecto.id
        self.db.delete(self.proyecto)
        self.db.flush()

        self.assertEqual(self.db.query(HistorialCambio).filter(HistorialCambio.id_proyecto == id_proyecto).count(), 0)


if __name__ == "__main__":
    unittest.main()
