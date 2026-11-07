"""CU18: cómo se compara una clase y cómo se cuenta lo que le pasó."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql://sin-conexion/pruebas")

from app.services.resumen_cambios import entrada_de_lote, entrada_de_tramo, tramos_entre, unir_tramos


def _item(id_, texto, tipo="String", visibilidad="publico") -> dict:
    return {"id": id_, "texto": texto, "tipo": tipo, "visibilidad": visibilidad}


def _clase(nombre="Cliente", atributos=(), metodos=(), id_=None, x=0) -> dict:
    return {
        "id": id_ or f"c-{nombre.lower()}",
        "type": "clase",
        "position": {"x": x, "y": 0},
        "data": {"nombre": nombre, "atributos": list(atributos), "metodos": list(metodos)},
    }


def _relacion(id_="r1", source="c-cliente", target="c-venta", tipo="asociacion", origen="1", destino="*", **data) -> dict:
    return {
        "id": id_,
        "source": source,
        "target": target,
        "type": "relacion",
        "data": {
            "tipo": tipo,
            "multiplicidadOrigen": origen,
            "multiplicidadDestino": destino,
            "nombre": None,
            "estiloLinea": "recta",
            **data,
        },
    }


def _diagrama(*nodos, relaciones=()) -> dict:
    return {"nodes": list(nodos), "edges": list(relaciones)}


def _resumenes(antes, despues, propia=None) -> list[str]:
    entradas = [entrada_de_tramo(t) for t in tramos_entre(antes, despues, propia)]
    return [e["resumen"] for e in entradas if e]


class ClaseTest(unittest.TestCase):
    def test_crear(self):
        self.assertEqual(_resumenes(_diagrama(), _diagrama(_clase())), ["creó la clase Cliente"])

    def test_crear_con_contenido(self):
        despues = _diagrama(_clase(atributos=[_item("a", "x"), _item("b", "y")], metodos=[_item("m", "z")]))
        self.assertEqual(_resumenes(_diagrama(), despues), ["creó la clase Cliente con 2 atributos y 1 método"])

    def test_eliminar_cuenta_sus_relaciones_sin_listarlas(self):
        otra = _clase("Venta")
        tercera = _clase("Pago")
        antes = _diagrama(
            _clase(), otra, tercera,
            relaciones=[_relacion(), _relacion("r2", target="c-pago")],
        )
        self.assertEqual(
            _resumenes(antes, _diagrama(otra, tercera)), ["eliminó la clase Cliente y sus 2 relaciones"]
        )

    def test_eliminar_con_una_relacion_y_sin_ninguna(self):
        otra = _clase("Venta")
        self.assertEqual(
            _resumenes(_diagrama(_clase(), otra, relaciones=[_relacion()]), _diagrama(otra)),
            ["eliminó la clase Cliente y su relación"],
        )
        self.assertEqual(_resumenes(_diagrama(_clase()), _diagrama()), ["eliminó la clase Cliente"])

    def test_renombrar(self):
        antes = _diagrama(_clase("Cliente", id_="c1"))
        despues = _diagrama(_clase("Comprador", id_="c1"))
        self.assertEqual(_resumenes(antes, despues), ["renombró la clase Cliente a Comprador"])

    def test_el_nombre_se_conserva_al_eliminar(self):
        tramo = tramos_entre(_diagrama(_clase()), _diagrama())[0]
        entrada = entrada_de_tramo(tramo)
        self.assertEqual(entrada["nombre_elemento"], "Cliente")
        self.assertEqual(entrada["tipo_operacion"], "eliminar_clase")
        self.assertEqual(entrada["detalle"]["antes"]["clase"]["nombre"], "Cliente")
        self.assertIsNone(entrada["detalle"]["despues"]["clase"])


class ElementosTest(unittest.TestCase):
    def _cambio(self, atributos_antes, atributos_despues, metodos_antes=(), metodos_despues=()):
        return _resumenes(
            _diagrama(_clase(atributos=atributos_antes, metodos=metodos_antes)),
            _diagrama(_clase(atributos=atributos_despues, metodos=metodos_despues)),
        )

    def test_agregar_uno_y_varios(self):
        self.assertEqual(self._cambio([], [_item("a", "email")]), ["agregó el atributo email a Cliente"])
        self.assertEqual(
            self._cambio([], [_item("a", "email"), _item("b", "telefono")]),
            ["agregó los atributos email y telefono a Cliente"],
        )

    def test_eliminar(self):
        self.assertEqual(self._cambio([_item("a", "email")], []), ["eliminó el atributo email de Cliente"])

    def test_metodo(self):
        self.assertEqual(self._cambio([], [], [], [_item("m", "pagar")]), ["agregó el método pagar a Cliente"])

    def test_renombrar_conserva_el_id(self):
        self.assertEqual(
            self._cambio([_item("a", "mail")], [_item("a", "email")]), ["renombró el atributo mail a email en Cliente"]
        )

    def test_tipo(self):
        self.assertEqual(
            self._cambio([_item("a", "edad", "String")], [_item("a", "edad", "int")]),
            ["cambió el tipo de edad de String a int en Cliente"],
        )

    def test_visibilidad(self):
        self.assertEqual(
            self._cambio([_item("a", "saldo")], [_item("a", "saldo", visibilidad="privado")]),
            ["cambió la visibilidad de saldo a privado en Cliente"],
        )

    def test_varios_tipos_de_cambio_en_una_frase(self):
        self.assertEqual(
            self._cambio(
                [_item("a", "mail"), _item("b", "saldo")],
                [_item("a", "email"), _item("b", "saldo", visibilidad="privado")],
            ),
            ["renombró el atributo mail a email, y cambió la visibilidad de saldo a privado en Cliente"],
        )

    def test_ids_regenerados_no_son_un_cambio(self):
        self.assertEqual(self._cambio([_item("viejo", "email")], [_item("nuevo", "email")]), [])

    def test_el_orden_no_es_un_cambio(self):
        a, b = _item("a", "x"), _item("b", "y")
        self.assertEqual(self._cambio([a, b], [b, a]), [])

    def test_un_item_sin_nombre_no_cuenta_hasta_tener_nombre(self):
        self.assertEqual(self._cambio([], [_item("a", "  ")]), [])

    def test_mas_de_tres_frases_se_recortan_pero_quedan_en_el_detalle(self):
        antes = [_item(str(i), f"a{i}") for i in range(5)]
        despues = [_item(str(i), f"b{i}") for i in range(5)]
        tramo = tramos_entre(_diagrama(_clase(atributos=antes)), _diagrama(_clase(atributos=despues)))[0]
        entrada = entrada_de_tramo(tramo)
        self.assertIn("y 2 cambios más", entrada["resumen"].replace(", y", " y"))
        self.assertEqual(len(entrada["detalle"]["cambios"]), 5)


class RelacionesTest(unittest.TestCase):
    def setUp(self):
        self.clases = (_clase(), _clase("Venta"))

    def _con(self, *relaciones):
        return _diagrama(*self.clases, relaciones=relaciones)

    def test_crear(self):
        self.assertEqual(
            _resumenes(self._con(), self._con(_relacion())), ["creó una asociación entre Cliente (1) y Venta (*)"]
        )

    def test_crear_sin_multiplicidades(self):
        relacion = _relacion(tipo="herencia", origen=None, destino=None)
        self.assertEqual(_resumenes(self._con(), self._con(relacion)), ["creó una herencia entre Cliente y Venta"])

    def test_eliminar(self):
        self.assertEqual(_resumenes(self._con(_relacion()), self._con()), ["eliminó la asociación entre Cliente y Venta"])

    def test_multiplicidad(self):
        self.assertEqual(
            _resumenes(self._con(_relacion(destino="1")), self._con(_relacion(destino="*"))),
            ["cambió la multiplicidad de Cliente–Venta: Venta de 1 a *"],
        )

    def test_tipo(self):
        self.assertEqual(
            _resumenes(self._con(_relacion()), self._con(_relacion(tipo="composicion"))),
            ["cambió el tipo de Cliente–Venta de asociación a composición"],
        )

    def test_el_estilo_de_linea_no_es_un_cambio(self):
        self.assertEqual(_resumenes(self._con(_relacion()), self._con(_relacion(estiloLinea="curva"))), [])

    def test_va_a_una_sola_clase(self):
        tramos = tramos_entre(self._con(), self._con(_relacion()))
        self.assertEqual([t.clase_id for t in tramos], ["c-cliente"])

    def test_va_a_la_clase_seleccionada_si_es_uno_de_los_extremos(self):
        tramos = tramos_entre(self._con(), self._con(_relacion()), propia="c-venta")
        self.assertEqual([t.clase_id for t in tramos], ["c-venta"])

    def test_el_detalle_nombra_las_dos_clases_para_el_filtro(self):
        tramo = tramos_entre(self._con(), self._con(_relacion()))[0]
        self.assertEqual(entrada_de_tramo(tramo)["detalle"]["ids_clases"], ["c-cliente", "c-venta"])

    def test_perder_la_clase_intermedia_porque_se_elimino_no_es_otro_cambio(self):
        intermedia = _clase("Detalle")
        antes = _diagrama(*self.clases, intermedia, relaciones=[_relacion(claseAsociacion="c-detalle")])
        despues = _diagrama(*self.clases, relaciones=[_relacion(claseAsociacion=None)])
        self.assertEqual(_resumenes(antes, despues), ["eliminó la clase Detalle"])

    def test_asignar_clase_intermedia(self):
        intermedia = _clase("Detalle")
        antes = _diagrama(*self.clases, intermedia, relaciones=[_relacion()])
        despues = _diagrama(*self.clases, intermedia, relaciones=[_relacion(claseAsociacion="c-detalle")])
        self.assertEqual(_resumenes(antes, despues), ["asignó Detalle como clase intermedia de Cliente–Venta"])


class SinCambiosTest(unittest.TestCase):
    def test_mover_una_clase_no_genera_nada(self):
        self.assertEqual(tramos_entre(_diagrama(_clase(x=0)), _diagrama(_clase(x=500))), [])

    def test_contenido_invalido_no_rompe(self):
        self.assertEqual(tramos_entre({}, {"nodes": "x", "edges": None}), [])


class UnirTramosTest(unittest.TestCase):
    def _unidos(self, *versiones):
        tramo = None
        for antes, despues in zip(versiones, versiones[1:]):
            for siguiente in tramos_entre(antes, despues):
                tramo = siguiente if tramo is None else unir_tramos(tramo, siguiente)
        return tramo

    def test_junta_los_cambios_de_varios_mensajes(self):
        tramo = self._unidos(
            _diagrama(_clase()),
            _diagrama(_clase(atributos=[_item("a", "e")])),
            _diagrama(_clase(atributos=[_item("a", "email")])),
            _diagrama(_clase(atributos=[_item("a", "email"), _item("b", "telefono")])),
        )
        self.assertEqual(entrada_de_tramo(tramo)["resumen"], "agregó los atributos email y telefono a Cliente")

    def test_agregar_y_borrar_lo_mismo_no_deja_nada(self):
        tramo = self._unidos(_diagrama(_clase()), _diagrama(_clase(atributos=[_item("a", "x")])), _diagrama(_clase()))
        self.assertIsNone(entrada_de_tramo(tramo))

    def test_crear_y_eliminar_la_clase_no_deja_nada(self):
        tramo = self._unidos(_diagrama(), _diagrama(_clase()), _diagrama())
        self.assertIsNone(entrada_de_tramo(tramo))

    def test_crear_y_borrar_una_relacion_no_deja_nada(self):
        clases = (_clase(), _clase("Venta"))
        tramo = self._unidos(_diagrama(*clases), _diagrama(*clases, relaciones=[_relacion()]), _diagrama(*clases))
        self.assertIsNone(entrada_de_tramo(tramo))

    def test_crear_la_clase_y_agregarle_cosas_cuenta_como_crearla(self):
        tramo = self._unidos(_diagrama(), _diagrama(_clase()), _diagrama(_clase(atributos=[_item("a", "x")])))
        self.assertEqual(entrada_de_tramo(tramo)["resumen"], "creó la clase Cliente con 1 atributo")
        self.assertEqual(entrada_de_tramo(tramo)["tipo_operacion"], "crear_clase")


class LoteTest(unittest.TestCase):
    def test_importacion_cuenta_lo_que_quedo(self):
        antes = _diagrama(_clase("Vieja"))
        despues = _diagrama(_clase(), _clase("Venta"), relaciones=[_relacion()])
        entrada = entrada_de_lote("importacion", antes, despues)
        self.assertEqual(entrada["resumen"], "importó 2 clases y 1 relación")
        self.assertEqual(entrada["tipo_operacion"], "importar")
        self.assertIsNone(entrada["id_elemento"])

    def test_foto_cuenta_solo_lo_agregado(self):
        existente = _clase("Vieja")
        entrada = entrada_de_lote("foto", _diagrama(existente), _diagrama(existente, _clase()))
        self.assertEqual(entrada["resumen"], "digitalizó por foto 1 clase y 0 relaciones")
        self.assertEqual(entrada["detalle"]["ids_clases"], ["c-cliente"])


if __name__ == "__main__":
    unittest.main()
