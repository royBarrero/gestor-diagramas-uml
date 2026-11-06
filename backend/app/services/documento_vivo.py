"""La versión viva de cada diagrama: en memoria, por proyecto, mientras haya
alguien conectado. Es la referencia para los cambios del agente (CU17) y para lo
que se guarda en la base.

Por qué existe: el autoguardado de cada cliente manda su diagrama completo, que
puede estar viejo; si se escribiera tal cual, pisaría cambios ajenos. Con esto el
autoguardado escribe esta versión, y lo único que la modifica son los cambios que
cada cliente dice haber hecho (`cambios`) y las operaciones del servidor.

Los contenidos se tratan como inmutables: nunca se modifican en el lugar, se
reemplazan, así que un hilo puede leerlos sin candados. Alcanza para el único
worker con el que corre el backend (ver Dockerfile).
"""

import hashlib
import json

_CAMPOS_NODO_LOCALES = ("selected", "dragging")
_CAMPOS_EDGE_LOCALES = ("selected",)
_CAMPOS_NODO_MEDIDAS = ("measured", "width", "height")


def _sin_campos(elemento: dict, campos: tuple[str, ...]) -> dict:
    return {clave: valor for clave, valor in elemento.items() if clave not in campos}


def _elementos(lista, campos: tuple[str, ...]) -> dict[str, dict]:
    if not isinstance(lista, list):
        return {}
    return {
        e["id"]: _sin_campos(e, campos)
        for e in lista
        if isinstance(e, dict) and isinstance(e.get("id"), str)
    }


def _sin_referencias_rotas(nodes: dict[str, dict], edges: dict[str, dict]) -> dict:
    """Misma regla que los clientes al fusionar: una clase pudo borrarse de un lado
    mientras del otro se le agregaba una relación."""
    relaciones = []
    for edge in edges.values():
        if edge.get("source") not in nodes or edge.get("target") not in nodes:
            continue
        data = edge.get("data") if isinstance(edge.get("data"), dict) else {}
        clase_asociacion = data.get("claseAsociacion")
        if clase_asociacion and clase_asociacion not in nodes:
            edge = {**edge, "data": {**data, "claseAsociacion": None}}
        relaciones.append(edge)
    return {"nodes": list(nodes.values()), "edges": relaciones}


def normalizar_contenido(contenido) -> dict:
    contenido = contenido if isinstance(contenido, dict) else {}
    return _sin_referencias_rotas(
        _elementos(contenido.get("nodes"), _CAMPOS_NODO_LOCALES),
        _elementos(contenido.get("edges"), _CAMPOS_EDGE_LOCALES),
    )


def _firma(valor) -> str:
    return json.dumps(valor, sort_keys=True, ensure_ascii=False, default=str)


def _firmas(contenido: dict, excluidos_nodo: tuple[str, ...] = _CAMPOS_NODO_MEDIDAS) -> tuple[dict, dict]:
    nodos = {n["id"]: _firma(_sin_campos(n, excluidos_nodo)) for n in contenido["nodes"]}
    relaciones = {e["id"]: _firma(e) for e in contenido["edges"]}
    return nodos, relaciones


def _ids_distintos(antes: dict, despues: dict) -> list[str]:
    ids = [id_ for id_, firma in despues.items() if antes.get(id_) != firma]
    return ids + [id_ for id_ in antes if id_ not in despues]


def calcular_cambios(antes: dict, despues: dict) -> dict:
    """Ids de lo que difiere entre dos contenidos, incluido lo borrado: es lo que
    los clientes aplican al recibir un `cambio_diagrama`."""
    nodos_antes, relaciones_antes = _firmas(antes)
    nodos_despues, relaciones_despues = _firmas(despues)
    return {
        "nodes": _ids_distintos(nodos_antes, nodos_despues),
        "edges": _ids_distintos(relaciones_antes, relaciones_despues),
    }


def huella_sin_posiciones(contenido: dict) -> str:
    """Identifica el contenido sin contar dónde están las clases en el lienzo:
    moverlas no impide deshacer un cambio del agente."""
    nodos, relaciones = _firmas(contenido, (*_CAMPOS_NODO_MEDIDAS, "position"))
    return hashlib.sha256(_firma([nodos, relaciones]).encode("utf-8")).hexdigest()


def restaurar_con_posiciones_actuales(copia: dict, actual: dict) -> dict:
    """La copia, pero cada clase que sigue existiendo queda donde está ahora."""
    posiciones = {n["id"]: n.get("position") for n in actual["nodes"]}
    return {
        "nodes": [
            {**n, "position": posiciones[n["id"]]} if posiciones.get(n["id"]) else n
            for n in copia["nodes"]
        ],
        "edges": copia["edges"],
    }


class DocumentosVivos:
    def __init__(self):
        self._contenidos: dict[int, dict] = {}

    def abrir(self, proyecto_id: int, contenido) -> dict:
        """Si ya hay gente conectada, su versión está más al día que la base."""
        return self._contenidos.setdefault(proyecto_id, normalizar_contenido(contenido))

    def cerrar(self, proyecto_id: int) -> None:
        self._contenidos.pop(proyecto_id, None)

    def obtener(self, proyecto_id: int) -> dict | None:
        return self._contenidos.get(proyecto_id)

    def aplicar_mensaje(self, proyecto_id: int, data) -> dict | None:
        """Aplica un mensaje de un cliente. Devuelve el contenido resultante, o None
        si no hay documento abierto o el mensaje no es un diagrama.

        Con `cambios` se toma solo lo que el cliente dice haber cambiado: el resto
        de su diagrama puede estar viejo. Sin `cambios`, se toma todo.
        """
        actual = self._contenidos.get(proyecto_id)
        if actual is None or not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
            return None

        cambios = data.get("cambios")
        if not isinstance(cambios, dict):
            return self.reemplazar_y_devolver(proyecto_id, data)

        nodos = _elementos(actual["nodes"], _CAMPOS_NODO_LOCALES)
        relaciones = _elementos(actual["edges"], _CAMPOS_EDGE_LOCALES)
        self._aplicar_ids(nodos, _elementos(data.get("nodes"), _CAMPOS_NODO_LOCALES), cambios.get("nodes"))
        self._aplicar_ids(relaciones, _elementos(data.get("edges"), _CAMPOS_EDGE_LOCALES), cambios.get("edges"))
        contenido = _sin_referencias_rotas(nodos, relaciones)
        self._contenidos[proyecto_id] = contenido
        return contenido

    @staticmethod
    def _aplicar_ids(actuales: dict, recibidos: dict, ids) -> None:
        for id_ in ids if isinstance(ids, list) else []:
            if not isinstance(id_, str):
                continue
            if id_ in recibidos:
                actuales[id_] = recibidos[id_]
            else:
                actuales.pop(id_, None)

    def reemplazar_y_devolver(self, proyecto_id: int, contenido) -> dict:
        normalizado = normalizar_contenido(contenido)
        self._contenidos[proyecto_id] = normalizado
        return normalizado

    def reemplazar(self, proyecto_id: int, contenido) -> dict:
        """Para cambios hechos en el servidor. Devuelve los `cambios` a difundir; si
        no había documento abierto no queda ninguno, porque no hay nadie conectado."""
        nuevo = normalizar_contenido(contenido)
        actual = self._contenidos.get(proyecto_id)
        if actual is None:
            return calcular_cambios(nuevo, nuevo)
        self._contenidos[proyecto_id] = nuevo
        return calcular_cambios(actual, nuevo)
