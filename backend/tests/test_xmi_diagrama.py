"""CU10: ida y vuelta del XMI (export -> import devuelve el mismo diagrama) y
forma que necesita Enterprise Architect para mostrar tipos de atributos y
firmas de métodos. No usa la base."""

import unittest
from xml.etree import ElementTree as ET

from app.services.exportacion_diagrama import validar_contenido
from app.services.xmi_diagrama import (
    NS_UML,
    NS_XMI,
    XMI_ID,
    XMI_IDREF,
    _parsear_firma,
    contenido_a_xmi,
    xmi_a_contenido,
)


def _item(id_, texto, tipo="", visibilidad="publico"):
    return {"id": id_, "visibilidad": visibilidad, "tipo": tipo, "texto": texto}


def _clase(id_, nombre, atributos=(), metodos=()):
    return {
        "id": id_,
        "type": "clase",
        "position": {"x": 0, "y": 0},
        "data": {"nombre": nombre, "atributos": list(atributos), "metodos": list(metodos)},
    }


def _relacion(id_, source, target, tipo, mult_o=None, mult_d=None, nombre=None, clase_asociacion=None):
    return {
        "id": id_,
        "source": source,
        "target": target,
        "type": "relacion",
        "data": {
            "tipo": tipo,
            "multiplicidadOrigen": mult_o,
            "multiplicidadDestino": mult_d,
            "nombre": nombre,
            "estiloLinea": "recta",
            "claseAsociacion": clase_asociacion,
        },
    }


def _diagrama_de_prueba() -> dict:
    return {
        "nodes": [
            _clase(
                "venta",
                "Venta",
                atributos=[
                    _item("venta-estado", "estado", "String", "privado"),
                    _item("venta-total", "total", "float"),
                    _item("venta-materia", "materia", "Materia"),
                ],
                metodos=[
                    _item("venta-inscribir", "inscribir(materia: Materia): Materia"),
                    _item("venta-anular", "anular(): void"),
                    _item("venta-calcular", "calcularTotal(): float", visibilidad="protegido"),
                    _item("venta-descontar", "descontarStock(cantidad: int): void"),
                    _item("venta-cerrar", "cerrar()"),
                    _item("venta-aplicar", "aplicarDescuento(porcentaje: float, motivo: String): boolean"),
                ],
            ),
            _clase("producto", "Producto", atributos=[_item("producto-nombre", "nombre", "String")]),
            _clase("persona", "Persona"),
            _clase("materia", "Materia"),
            _clase("cliente", "Cliente", metodos=[_item("cliente-saludar", "saludar(otro): String")]),
            _clase("linea", "LineaVenta", atributos=[_item("linea-cantidad", "cantidad", "int")]),
        ],
        "edges": [
            _relacion("rel-herencia", "cliente", "persona", "herencia"),
            _relacion("rel-composicion", "venta", "producto", "composicion", "1", "0..*"),
            _relacion("rel-dependencia", "cliente", "producto", "dependencia", nombre="usa"),
            _relacion("rel-compra", "cliente", "venta", "asociacion", "1", "1..*", clase_asociacion="linea"),
        ],
    }


def _sin_posiciones(contenido: dict) -> dict:
    contenido = validar_contenido(contenido)
    for node in contenido["nodes"]:
        node["position"] = None
    contenido["nodes"].sort(key=lambda n: n["id"])
    contenido["edges"].sort(key=lambda e: e["id"])
    return contenido


class IdaYVueltaTest(unittest.TestCase):
    def test_exportar_e_importar_devuelve_el_mismo_diagrama(self):
        original = _diagrama_de_prueba()
        importado = xmi_a_contenido(contenido_a_xmi(original, "Ventas").encode("utf-8"))
        self.assertEqual(_sin_posiciones(importado), _sin_posiciones(original))

    def test_metodo_sin_parentesis_vuelve_con_parentesis(self):
        original = {"nodes": [_clase("a", "A", metodos=[_item("a-m", "cerrar")])], "edges": []}
        importado = xmi_a_contenido(contenido_a_xmi(original, "D").encode("utf-8"))
        self.assertEqual(importado["nodes"][0]["data"]["metodos"][0]["texto"], "cerrar()")

    def test_retorno_cargado_en_tipo_del_metodo_viaja_en_la_firma(self):
        original = {"nodes": [_clase("a", "A", metodos=[_item("a-m", "total()", tipo="float")])], "edges": []}
        importado = xmi_a_contenido(contenido_a_xmi(original, "D").encode("utf-8"))
        self.assertEqual(importado["nodes"][0]["data"]["metodos"][0]["texto"], "total(): float")


class FormaExportadaTest(unittest.TestCase):
    def setUp(self):
        self.xmi = ET.fromstring(contenido_a_xmi(_diagrama_de_prueba(), "Ventas"))
        self.modelo = self.xmi.find(f"{{{NS_UML}}}Model")
        self.primitivos = {
            e.get(XMI_ID): e.get("name")
            for e in self.modelo.findall("packagedElement")
            if e.get(f"{{{NS_XMI}}}type") == "uml:PrimitiveType"
        }
        self.tipo_de = lambda elem: self.primitivos.get(elem.find("type").get(XMI_IDREF))

    def _operacion(self, op_id):
        return next(op for op in self.modelo.iter("ownedOperation") if op.get(XMI_ID) == op_id)

    def test_documentation_de_ea_es_el_primer_hijo(self):
        primero, segundo = list(self.xmi)[:2]
        self.assertEqual(primero.tag, f"{{{NS_XMI}}}Documentation")
        self.assertEqual(primero.get("exporter"), "Enterprise Architect")
        self.assertEqual(primero.get("exporterVersion"), "6.5")
        self.assertEqual(segundo.tag, f"{{{NS_UML}}}Model")

    def test_tipo_que_es_clase_referencia_la_clase(self):
        attr = next(a for a in self.modelo.iter("ownedAttribute") if a.get(XMI_ID) == "venta-materia")
        self.assertEqual(attr.find("type").get(XMI_IDREF), "materia")
        entrada, retorno = self._operacion("venta-inscribir").findall("ownedParameter")
        self.assertEqual(entrada.find("type").get(XMI_IDREF), "materia")
        self.assertEqual(retorno.find("type").get(XMI_IDREF), "materia")

        nombres_primitivos = set(self.primitivos.values())
        self.assertNotIn("Materia", nombres_primitivos)
        self.assertTrue({"String", "int", "void"} <= nombres_primitivos)

    def test_operacion_con_parametro_y_retorno(self):
        op = self._operacion("venta-descontar")
        self.assertEqual(op.get("name"), "descontarStock")
        entrada, retorno = op.findall("ownedParameter")
        self.assertEqual((entrada.get("name"), entrada.get("direction"), self.tipo_de(entrada)), ("cantidad", "in", "int"))
        self.assertEqual((retorno.get("direction"), self.tipo_de(retorno)), ("return", "void"))

    def test_operacion_sin_retorno_no_tiene_parametro_return(self):
        op = self._operacion("venta-cerrar")
        self.assertEqual(op.get("name"), "cerrar")
        self.assertEqual(op.findall("ownedParameter"), [])

    def test_atributo_mantiene_type_idref_estandar(self):
        attr = next(a for a in self.modelo.iter("ownedAttribute") if a.get(XMI_ID) == "venta-estado")
        self.assertEqual(self.tipo_de(attr), "String")

    def test_extension_de_ea_con_tipos(self):
        extension = self.xmi.find(f"{{{NS_XMI}}}Extension")
        self.assertIsNotNone(extension)
        self.assertEqual(extension.get("extender"), "Enterprise Architect")
        venta = next(e for e in extension.iter("element") if e.get(XMI_IDREF) == "venta")

        estado = next(a for a in venta.iter("attribute") if a.get(XMI_IDREF) == "venta-estado")
        self.assertEqual(estado.get("name"), "estado")
        self.assertEqual(estado.get("scope"), "Private")
        self.assertEqual(estado.find("properties").get("type"), "String")

        operaciones = {op.get(XMI_IDREF): op for op in venta.iter("operation")}
        self.assertEqual(operaciones["venta-anular"].get("name"), "anular")
        self.assertEqual(operaciones["venta-anular"].find("type").get("type"), "void")
        self.assertIsNone(operaciones["venta-cerrar"].find("type"))
        param = operaciones["venta-descontar"].find("parameters/parameter")
        self.assertEqual(param.find("properties").get("type"), "int")

        clase_asociacion = next(e for e in extension.iter("element") if e.get(XMI_IDREF) == "linea")
        self.assertEqual(clase_asociacion.get(f"{{{NS_XMI}}}type"), "uml:AssociationClass")


_XMI_ESTILO_EA = b"""<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.1" xmlns:uml="http://schema.omg.org/spec/UML/2.1" xmlns:xmi="http://schema.omg.org/spec/XMI/2.1">
  <uml:Model xmi:type="uml:Model" name="EA_Model">
    <packagedElement xmi:type="uml:Class" xmi:id="EAID_VENTA" name="Venta">
      <ownedAttribute xmi:type="uml:Property" xmi:id="EAID_ESTADO" name="estado" visibility="private">
        <type xmi:idref="EAID_DESCONOCIDO"/>
      </ownedAttribute>
      <ownedAttribute xmi:type="uml:Property" xmi:id="EAID_TOTAL" name="total" visibility="public">
        <type xmi:idref="EAJava_float"/>
      </ownedAttribute>
      <ownedOperation xmi:id="EAID_DESCONTAR" name="descontarStock" visibility="public">
        <ownedParameter xmi:id="EAID_P1" name="cantidad" direction="in" type="EAJava_int"/>
        <ownedParameter xmi:id="EAID_RT" name="return" direction="return" type="EAJava_void"/>
      </ownedOperation>
      <ownedOperation xmi:id="EAID_CERRAR" name="cerrar" visibility="public"/>
    </packagedElement>
  </uml:Model>
  <xmi:Extension extender="Enterprise Architect" extenderID="6.5">
    <elements>
      <element xmi:idref="EAID_VENTA" xmi:type="uml:Class" name="Venta" scope="public">
        <attributes>
          <attribute xmi:idref="EAID_ESTADO" name="estado" scope="Private"><properties type="String"/></attribute>
          <attribute xmi:idref="EAID_TOTAL" name="total" scope="Public"><properties type="float"/></attribute>
        </attributes>
        <operations>
          <operation xmi:idref="EAID_DESCONTAR" name="descontarStock" scope="Public">
            <type type="void"/>
            <parameters><parameter xmi:idref="EAID_P1"><properties pos="0" type="int" ck="in"/></parameter></parameters>
          </operation>
          <operation xmi:idref="EAID_CERRAR" name="cerrar" scope="Public"><type type="void"/></operation>
        </operations>
      </element>
    </elements>
  </xmi:Extension>
</xmi:XMI>
"""


class ImportacionEATest(unittest.TestCase):
    def _clase(self, contenido):
        return contenido["nodes"][0]["data"]

    def test_tipos_y_firmas_desde_xmi_de_ea(self):
        data = self._clase(xmi_a_contenido(_XMI_ESTILO_EA))
        self.assertEqual([(a["texto"], a["tipo"]) for a in data["atributos"]], [("estado", "String"), ("total", "float")])
        self.assertEqual(
            [m["texto"] for m in data["metodos"]], ["descontarStock(cantidad: int): void", "cerrar(): void"]
        )

    def test_fallback_por_extension_rearma_firmas(self):
        # Sin clases en el modelo UML se lee solo la extensión.
        xmi = _XMI_ESTILO_EA.replace(b'xmi:type="uml:Class" xmi:id="EAID_VENTA"', b'xmi:type="uml:Package" xmi:id="EAID_VENTA"')
        data = self._clase(xmi_a_contenido(xmi))
        self.assertEqual(data["atributos"][0]["tipo"], "String")
        self.assertEqual(
            [m["texto"] for m in data["metodos"]], ["descontarStock(cantidad: int): void", "cerrar(): void"]
        )

    def test_tipo_que_referencia_una_clase_sin_extension_ea(self):
        xmi = b"""<?xml version="1.0"?>
<xmi:XMI xmi:version="2.1" xmlns:uml="http://schema.omg.org/spec/UML/2.1" xmlns:xmi="http://schema.omg.org/spec/XMI/2.1">
  <xmi:Documentation exporter="Enterprise Architect" exporterVersion="6.5"/>
  <uml:Model xmi:id="m" name="D">
    <packagedElement xmi:type="uml:Class" xmi:id="alumno" name="Alumno">
      <ownedAttribute xmi:type="uml:Property" xmi:id="alumno-materia" name="materia" visibility="public">
        <type xmi:idref="materia"/>
      </ownedAttribute>
      <ownedOperation xmi:type="uml:Operation" xmi:id="alumno-inscribir" name="inscribir" visibility="public">
        <ownedParameter xmi:type="uml:Parameter" xmi:id="alumno-inscribir-p0" name="materia" direction="in">
          <type xmi:idref="materia"/>
        </ownedParameter>
      </ownedOperation>
    </packagedElement>
    <packagedElement xmi:type="uml:Class" xmi:id="materia" name="Materia"/>
  </uml:Model>
</xmi:XMI>"""
        data = self._clase(xmi_a_contenido(xmi))
        self.assertEqual(data["atributos"][0]["tipo"], "Materia")
        self.assertEqual(data["metodos"][0]["texto"], "inscribir(materia: Materia)")

    def test_xmi_viejo_con_firma_completa_en_el_nombre(self):
        xmi = b"""<?xml version="1.0"?>
<xmi:XMI xmi:version="2.1" xmlns:uml="http://schema.omg.org/spec/UML/2.1" xmlns:xmi="http://schema.omg.org/spec/XMI/2.1">
  <uml:Model xmi:id="m" name="D">
    <packagedElement xmi:type="uml:Class" xmi:id="a" name="A">
      <ownedOperation xmi:type="uml:Operation" xmi:id="a-m" name="anular(): void" visibility="public"/>
    </packagedElement>
  </uml:Model>
</xmi:XMI>"""
        self.assertEqual(self._clase(xmi_a_contenido(xmi))["metodos"][0]["texto"], "anular(): void")


class ParsearFirmaTest(unittest.TestCase):
    def test_casos(self):
        casos = {
            "anular(): void": ("anular", [], "void"),
            "cerrar()": ("cerrar", [], None),
            "cerrar": ("cerrar", [], None),
            "total: float": ("total", [], "float"),
            "  descontarStock( cantidad : int ) :  void ": ("descontarStock", [("cantidad", "int")], "void"),
            "saludar(otro, veces: int)": ("saludar", [("otro", ""), ("veces", "int")], None),
            "listar(): List<String>": ("listar", [], "List<String>"),
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(_parsear_firma(texto), esperado)


if __name__ == "__main__":
    unittest.main()
