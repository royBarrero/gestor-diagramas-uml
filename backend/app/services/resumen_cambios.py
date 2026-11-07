"""CU18: qué cambió entre dos versiones de un diagrama y cómo se cuenta. Funciones
puras: sin base, sin estado, sin tiempo real.

La lista de cambios se calcula una sola vez, y de ella salen el resumen y el `detalle`
de cada entrada, así que nunca se contradicen.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.services.constantes_diagrama import normalizar
from app.services.documento_vivo import normalizar_contenido

MAX_FRASES = 3

_CAMPOS = {"atributos": ("el atributo", "los atributos"), "metodos": ("el método", "los métodos")}
_ETIQUETA_RELACION = {
    "asociacion": "asociación",
    "herencia": "herencia",
    "agregacion": "agregación",
    "composicion": "composición",
    "dependencia": "dependencia",
}
_TIPO_DE_OPERACION = {
    "crear_clase": "crear_clase",
    "eliminar_clase": "eliminar_clase",
    "crear_relacion": "crear_relacion",
    "editar_relacion": "editar_relacion",
    "eliminar_relacion": "eliminar_relacion",
}


# ---- Firmas: lo que cuenta como cambio. También las usa CU16. ----


def _items_normalizados(items) -> list:
    """Sin ids ni orden: reordenar una lista o regenerar ids no cambia la clase."""
    if not isinstance(items, list):
        return []
    filas = [[i.get("visibilidad"), i.get("tipo"), i.get("texto")] for i in items if isinstance(i, dict)]
    return sorted(filas, key=str)


def firma_clase(nodo: dict) -> list:
    """Solo lo que cuenta como cambio: moverla en el lienzo no cambia su firma."""
    data = nodo.get("data") if isinstance(nodo.get("data"), dict) else {}
    return [
        data.get("nombre"),
        _items_normalizados(data.get("atributos")),
        _items_normalizados(data.get("metodos")),
    ]


def firma_relacion(edge: dict) -> list:
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


# ---- Vistas: una clase o relación sin lo que es solo del lienzo ----


def _data(elemento: dict) -> dict:
    return elemento.get("data") if isinstance(elemento.get("data"), dict) else {}


def _vista_items(items) -> list[dict]:
    if not isinstance(items, list):
        return []
    return [
        {
            "id": i.get("id"),
            "nombre": str(i.get("texto") or "").strip(),
            "tipo": i.get("tipo") or "",
            "visibilidad": i.get("visibilidad"),
        }
        for i in items
        if isinstance(i, dict) and str(i.get("texto") or "").strip()
    ]


def _vista_clase(nodo: dict | None) -> dict | None:
    if nodo is None:
        return None
    data = _data(nodo)
    return {
        "nombre": str(data.get("nombre") or ""),
        "atributos": _vista_items(data.get("atributos")),
        "metodos": _vista_items(data.get("metodos")),
    }


def _nombre_de(*fuentes: dict) -> Callable[[str | None], str]:
    def nombre(clase_id) -> str:
        for fuente in fuentes:
            if clase_id in fuente:
                return str(_data(fuente[clase_id]).get("nombre") or "")
        return ""

    return nombre


def _vista_relacion(edge: dict, nombre) -> dict:
    data = _data(edge)
    return {
        "origen_id": edge.get("source"),
        "destino_id": edge.get("target"),
        "origen": nombre(edge.get("source")),
        "destino": nombre(edge.get("target")),
        "tipo": data.get("tipo"),
        "multiplicidadOrigen": data.get("multiplicidadOrigen"),
        "multiplicidadDestino": data.get("multiplicidadDestino"),
        "nombre": data.get("nombre"),
        "claseAsociacion": nombre(data.get("claseAsociacion")) if data.get("claseAsociacion") else None,
    }


# ---- Tramos: lo que le pasó a una clase entre dos versiones ----


@dataclass
class Tramo:
    """Una clase como estaba y como quedó, con las relaciones que le corresponden.
    Una clase que no existía, o que ya no existe, es None."""

    clase_id: str
    clase_antes: dict | None
    clase_despues: dict | None
    relaciones_antes: dict[str, dict] = field(default_factory=dict)
    relaciones_despues: dict[str, dict] = field(default_factory=dict)


def _clase_duena(extremos: tuple, nodos_antes: dict, nodos_despues: dict, propia: str | None) -> str:
    """Cada relación va a una sola clase, para que no salga dos veces: la que se eliminó
    con ella; si no, la que tiene seleccionada quien hizo el cambio; si no, la de origen."""
    eliminada = next((c for c in extremos if c in nodos_antes and c not in nodos_despues), None)
    if eliminada is not None:
        return eliminada
    return propia if propia in extremos else extremos[0]


def _solo_perdio_su_clase_intermedia(firma_antes: list | None, firma_despues: list | None, nodos: dict) -> bool:
    """Al eliminar una clase intermedia, sus relaciones la pierden solas: no es un cambio aparte."""
    if firma_antes is None or firma_despues is None or firma_antes[:-1] != firma_despues[:-1]:
        return False
    intermedia = firma_antes[-1]
    return bool(intermedia) and intermedia not in nodos and not firma_despues[-1]


def tramos_entre(antes: dict, despues: dict, propia: str | None = None) -> list[Tramo]:
    """Un tramo por cada clase que cambió, en el orden del diagrama. Moverlas no cuenta."""
    antes, despues = normalizar_contenido(antes), normalizar_contenido(despues)
    nodos_antes = {n["id"]: n for n in antes["nodes"]}
    nodos_despues = {n["id"]: n for n in despues["nodes"]}
    edges_antes = {e["id"]: e for e in antes["edges"]}
    edges_despues = {e["id"]: e for e in despues["edges"]}
    nombre_antes = _nombre_de(nodos_antes, nodos_despues)
    nombre_despues = _nombre_de(nodos_despues, nodos_antes)

    tramos: dict[str, Tramo] = {}

    def tramo_de(clase_id: str) -> Tramo:
        if clase_id not in tramos:
            tramos[clase_id] = Tramo(
                clase_id, _vista_clase(nodos_antes.get(clase_id)), _vista_clase(nodos_despues.get(clase_id))
            )
        return tramos[clase_id]

    for clase_id in [*nodos_despues, *(c for c in nodos_antes if c not in nodos_despues)]:
        anterior, actual = nodos_antes.get(clase_id), nodos_despues.get(clase_id)
        if anterior is None or actual is None or firma_clase(anterior) != firma_clase(actual):
            tramo_de(clase_id)

    for edge_id in [*edges_despues, *(e for e in edges_antes if e not in edges_despues)]:
        anterior, actual = edges_antes.get(edge_id), edges_despues.get(edge_id)
        firma_antes = firma_relacion(anterior) if anterior else None
        firma_despues = firma_relacion(actual) if actual else None
        if firma_antes == firma_despues or _solo_perdio_su_clase_intermedia(firma_antes, firma_despues, nodos_despues):
            continue
        referencia = actual or anterior
        extremos = (referencia.get("source"), referencia.get("target"))
        tramo = tramo_de(_clase_duena(extremos, nodos_antes, nodos_despues, propia))
        if anterior:
            tramo.relaciones_antes[edge_id] = _vista_relacion(anterior, nombre_antes)
        if actual:
            tramo.relaciones_despues[edge_id] = _vista_relacion(actual, nombre_despues)

    return list(tramos.values())


def unir_tramos(primero: Tramo, siguiente: Tramo) -> Tramo:
    """Lo que le pasó a la clase en los dos: como estaba al principio y como quedó al final."""
    relaciones_antes = dict(primero.relaciones_antes)
    relaciones_despues = dict(primero.relaciones_despues)
    for edge_id in {*siguiente.relaciones_antes, *siguiente.relaciones_despues}:
        ya_vista = edge_id in relaciones_antes or edge_id in relaciones_despues
        if not ya_vista and edge_id in siguiente.relaciones_antes:
            relaciones_antes[edge_id] = siguiente.relaciones_antes[edge_id]
        if edge_id in siguiente.relaciones_despues:
            relaciones_despues[edge_id] = siguiente.relaciones_despues[edge_id]
        else:
            relaciones_despues.pop(edge_id, None)
    return Tramo(
        primero.clase_id, primero.clase_antes, siguiente.clase_despues, relaciones_antes, relaciones_despues
    )


# ---- Comparación ----


def _emparejar(antes: list[dict], despues: list[dict]) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Primero por id; con lo que sobra, por nombre, por si se regeneraron los ids.
    Devuelve (parejas, eliminados, agregados)."""
    por_id = {i["id"]: i for i in despues if i.get("id")}
    parejas, sin_pareja = [], []
    usados = set()
    for item in antes:
        otro = por_id.get(item.get("id"))
        if otro is not None and otro["id"] not in usados:
            parejas.append((item, otro))
            usados.add(otro["id"])
        else:
            sin_pareja.append(item)

    restantes = [i for i in despues if i.get("id") not in usados]
    eliminados = []
    for item in sin_pareja:
        clave = normalizar(item["nombre"])
        otro = next((r for r in restantes if normalizar(r["nombre"]) == clave), None)
        if otro is None:
            eliminados.append(item)
        else:
            parejas.append((item, otro))
            restantes.remove(otro)
    return parejas, eliminados, restantes


def _comparar_items(campo: str, antes: list[dict], despues: list[dict]) -> list[dict]:
    parejas, eliminados, agregados = _emparejar(antes, despues)
    cambios = [{"op": "agregar", "campo": campo, "nombre": i["nombre"]} for i in agregados]
    cambios += [{"op": "eliminar", "campo": campo, "nombre": i["nombre"]} for i in eliminados]
    for anterior, actual in parejas:
        if anterior["nombre"] != actual["nombre"]:
            cambios.append({"op": "renombrar", "campo": campo, "de": anterior["nombre"], "a": actual["nombre"]})
        if campo == "atributos" and anterior["tipo"] != actual["tipo"]:
            cambios.append({"op": "tipo", "nombre": actual["nombre"], "de": anterior["tipo"], "a": actual["tipo"]})
        if anterior["visibilidad"] != actual["visibilidad"]:
            cambios.append(
                {
                    "op": "visibilidad",
                    "campo": campo,
                    "nombre": actual["nombre"],
                    "de": anterior["visibilidad"],
                    "a": actual["visibilidad"],
                }
            )
    return cambios


_CAMPOS_RELACION = ("tipo", "multiplicidadOrigen", "multiplicidadDestino", "nombre", "claseAsociacion")


def _comparar_relaciones(antes: dict[str, dict], despues: dict[str, dict]) -> list[dict]:
    cambios = []
    for edge_id, actual in despues.items():
        anterior = antes.get(edge_id)
        if anterior is None:
            cambios.append({"op": "crear_relacion", "relacion": actual})
            continue
        diferencias = {c: [anterior[c], actual[c]] for c in _CAMPOS_RELACION if anterior[c] != actual[c]}
        reconectada = (anterior["origen_id"], anterior["destino_id"]) != (actual["origen_id"], actual["destino_id"])
        if diferencias or reconectada:
            cambios.append(
                {
                    "op": "editar_relacion",
                    "relacion": actual,
                    "anterior": anterior,
                    "campos": diferencias,
                    "reconectada": reconectada,
                }
            )
    cambios += [{"op": "eliminar_relacion", "relacion": r} for edge_id, r in antes.items() if edge_id not in despues]
    return cambios


def comparar_clase(
    antes: dict | None,
    despues: dict | None,
    relaciones_antes: dict[str, dict] | None = None,
    relaciones_despues: dict[str, dict] | None = None,
) -> list[dict]:
    """La lista de cambios de una clase. Vacía si, al final, no cambió nada: por ejemplo,
    si se agregó y se borró lo mismo, o si se creó y se eliminó la clase en el mismo grupo."""
    relaciones_antes, relaciones_despues = relaciones_antes or {}, relaciones_despues or {}
    if antes is None and despues is None:
        return []
    if despues is None:
        return [{"op": "eliminar_clase", "clase": antes["nombre"], "relaciones": len(relaciones_antes)}]

    cambios = []
    if antes is None:
        cambios.append(
            {
                "op": "crear_clase",
                "clase": despues["nombre"],
                "atributos": len(despues["atributos"]),
                "metodos": len(despues["metodos"]),
            }
        )
    else:
        if antes["nombre"] != despues["nombre"]:
            cambios.append({"op": "renombrar_clase", "de": antes["nombre"], "a": despues["nombre"]})
        for campo in _CAMPOS:
            cambios += _comparar_items(campo, antes[campo], despues[campo])
    return cambios + _comparar_relaciones(relaciones_antes, relaciones_despues)


# ---- Textos ----


def _unir(partes: list[str]) -> str:
    return partes[0] if len(partes) == 1 else f'{", ".join(partes[:-1])} y {partes[-1]}'


def _contar(cantidad: int, singular: str, plural: str) -> str:
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def _elementos(cambios: list[dict], op: str, verbo: str) -> list[str]:
    frases = []
    for campo, (singular, plural) in _CAMPOS.items():
        nombres = [c["nombre"] for c in cambios if c["op"] == op and c["campo"] == campo]
        if nombres:
            frases.append(f"{verbo} {singular if len(nombres) == 1 else plural} {_unir(nombres)}")
    return frases


def _frase_creacion(cambio: dict) -> str:
    contenido = []
    if cambio["atributos"]:
        contenido.append(_contar(cambio["atributos"], "atributo", "atributos"))
    if cambio["metodos"]:
        contenido.append(_contar(cambio["metodos"], "método", "métodos"))
    return f'creó la clase {cambio["clase"]}' + (f" con {_unir(contenido)}" if contenido else "")


def _frase_eliminacion(cambio: dict) -> str:
    cantidad = cambio["relaciones"]
    if not cantidad:
        return f'eliminó la clase {cambio["clase"]}'
    relaciones = "su relación" if cantidad == 1 else f"sus {cantidad} relaciones"
    return f'eliminó la clase {cambio["clase"]} y {relaciones}'


def _extremo(clase: str, multiplicidad) -> str:
    return f"{clase} ({multiplicidad})" if multiplicidad else clase


def _par(relacion: dict) -> str:
    return f'{relacion["origen"]}–{relacion["destino"]}'


def _frases_edicion_relacion(cambio: dict) -> list[str]:
    relacion, anterior = cambio["relacion"], cambio["anterior"]
    par = _par(relacion)
    frases = [f"reconectó la relación {_par(anterior)} a {par}"] if cambio["reconectada"] else []
    for campo, (de, a) in cambio["campos"].items():
        if campo == "tipo":
            etiqueta_de = _ETIQUETA_RELACION.get(de, de)
            etiqueta_a = _ETIQUETA_RELACION.get(a, a)
            frases.append(f"cambió el tipo de {par} de {etiqueta_de} a {etiqueta_a}")
        elif campo == "multiplicidadOrigen":
            frases.append(f'cambió la multiplicidad de {par}: {relacion["origen"]} de {de or "-"} a {a or "-"}')
        elif campo == "multiplicidadDestino":
            frases.append(f'cambió la multiplicidad de {par}: {relacion["destino"]} de {de or "-"} a {a or "-"}')
        elif campo == "nombre":
            frases.append(f"le puso el nombre {a} a la relación {par}" if a else f"le quitó el nombre a la relación {par}")
        elif campo == "claseAsociacion":
            frases.append(f"asignó {a} como clase intermedia de {par}" if a else f"quitó la clase intermedia de {par}")
    return frases


def _frases_relaciones(cambios: list[dict]) -> list[str]:
    frases = []
    for cambio in cambios:
        relacion = cambio.get("relacion")
        if cambio["op"] == "crear_relacion":
            etiqueta = _ETIQUETA_RELACION.get(relacion["tipo"], "relación")
            origen = _extremo(relacion["origen"], relacion["multiplicidadOrigen"])
            destino = _extremo(relacion["destino"], relacion["multiplicidadDestino"])
            frases.append(f"creó una {etiqueta} entre {origen} y {destino}")
        elif cambio["op"] == "editar_relacion":
            frases += _frases_edicion_relacion(cambio)
        elif cambio["op"] == "eliminar_relacion":
            etiqueta = _ETIQUETA_RELACION.get(relacion["tipo"], "relación")
            frases.append(f'eliminó la {etiqueta} entre {relacion["origen"]} y {relacion["destino"]}')
    return frases


def _frases_elementos(cambios: list[dict]) -> list[str]:
    frases = []
    frases += _elementos(cambios, "agregar", "agregó")
    frases += _elementos(cambios, "eliminar", "eliminó")
    for cambio in cambios:
        if cambio["op"] == "renombrar":
            singular = _CAMPOS[cambio["campo"]][0]
            frases.append(f'renombró {singular} {cambio["de"]} a {cambio["a"]}')
        elif cambio["op"] == "tipo":
            frases.append(f'cambió el tipo de {cambio["nombre"]} de {cambio["de"] or "-"} a {cambio["a"] or "-"}')
        elif cambio["op"] == "visibilidad":
            frases.append(f'cambió la visibilidad de {cambio["nombre"]} a {cambio["a"]}')
    return frases


def _preposicion(cambios: list[dict]) -> str:
    ops = {c["op"] for c in cambios if c["op"] in ("agregar", "eliminar", "renombrar", "tipo", "visibilidad")}
    if ops == {"agregar"}:
        return "a"
    if ops == {"eliminar"}:
        return "de"
    return "en"


def redactar(cambios: list[dict], nombre_clase: str) -> str:
    """El resumen de una lista de cambios, sin el autor, que se muestra aparte."""
    frases = []
    for cambio in cambios:
        if cambio["op"] == "crear_clase":
            frases.append(_frase_creacion(cambio))
        elif cambio["op"] == "eliminar_clase":
            frases.append(_frase_eliminacion(cambio))
        elif cambio["op"] == "renombrar_clase":
            frases.append(f'renombró la clase {cambio["de"]} a {cambio["a"]}')

    de_elementos = _frases_elementos(cambios)
    if de_elementos:
        de_elementos[-1] += f" {_preposicion(cambios)} {nombre_clase}"
    frases += de_elementos + _frases_relaciones(cambios)

    if len(frases) > MAX_FRASES:
        restantes = len(frases) - MAX_FRASES
        frases = frases[:MAX_FRASES] + [_contar(restantes, "cambio más", "cambios más")]
    if len(frases) == 1:
        return frases[0]
    return f'{", ".join(frases[:-1])}, y {frases[-1]}'


def _tipo_operacion(cambios: list[dict]) -> str:
    tipos = {_TIPO_DE_OPERACION.get(c["op"], "editar_clase") for c in cambios}
    return tipos.pop() if len(tipos) == 1 else "editar_clase"


def entrada_de_tramo(tramo: Tramo, prefijo: str = "") -> dict | None:
    """Los campos de una entrada del historial, o None si no hay nada que contar."""
    cambios = comparar_clase(
        tramo.clase_antes, tramo.clase_despues, tramo.relaciones_antes, tramo.relaciones_despues
    )
    if not cambios:
        return None
    nombre = (tramo.clase_despues or tramo.clase_antes)["nombre"]
    relaciones = [*tramo.relaciones_antes.values(), *tramo.relaciones_despues.values()]
    ids_clases = {tramo.clase_id}
    for relacion in relaciones:
        ids_clases.update(i for i in (relacion["origen_id"], relacion["destino_id"]) if i)
    return {
        "tipo_operacion": _tipo_operacion(cambios),
        "id_elemento": tramo.clase_id,
        "nombre_elemento": nombre,
        "resumen": f"{prefijo}{redactar(cambios, nombre)}",
        "detalle": {
            "antes": {"clase": tramo.clase_antes, "relaciones": tramo.relaciones_antes},
            "despues": {"clase": tramo.clase_despues, "relaciones": tramo.relaciones_despues},
            "cambios": cambios,
            "ids_clases": sorted(ids_clases),
        },
    }


# ---- Foto e importación: una sola entrada por operación ----


def _cifras(contenido: dict) -> dict:
    return {
        "clases": [str(_data(n).get("nombre") or "") for n in contenido["nodes"]],
        "relaciones": len(contenido["edges"]),
    }


def _nuevos(contenido: dict, antes: dict, clave: str) -> list[dict]:
    existentes = {e["id"] for e in antes[clave]}
    return [e for e in contenido[clave] if e["id"] not in existentes]


def entrada_de_lote(origen: str, antes: dict, despues: dict) -> dict:
    """Foto: cuenta lo que agregó. Importación: reemplaza el diagrama, así que cuenta lo que quedó."""
    antes, despues = normalizar_contenido(antes), normalizar_contenido(despues)
    if origen == "foto":
        clases, relaciones = _nuevos(despues, antes, "nodes"), _nuevos(despues, antes, "edges")
        verbo, tipo = "digitalizó por foto", "digitalizar"
    else:
        clases, relaciones = despues["nodes"], despues["edges"]
        verbo, tipo = "importó", "importar"
    resumen = (
        f'{verbo} {_contar(len(clases), "clase", "clases")} '
        f'y {_contar(len(relaciones), "relación", "relaciones")}'
    )
    return {
        "tipo_operacion": tipo,
        "id_elemento": None,
        "nombre_elemento": None,
        "resumen": resumen,
        "detalle": {
            "antes": _cifras(antes),
            "despues": _cifras(despues),
            "cambios": [{"op": tipo, "clases": len(clases), "relaciones": len(relaciones)}],
            "ids_clases": [c["id"] for c in clases],
        },
    }
