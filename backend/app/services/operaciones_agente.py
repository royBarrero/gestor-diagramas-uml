"""CU17: aplica los cambios que un integrante le pide al agente de IA.

Las operaciones se aplican todas o ninguna. Parten de la versión viva del diagrama
(no de la base, que puede estar atrasada), y llegan a los clientes por el mismo
`cambio_diagrama` de CU07, con `cambios`, para que se fusionen sin pisar ediciones.
"""

import asyncio
import logging

from app.core.database import SessionLocal
from app.core.permisos import rol_de_usuario_en_proyecto
from app.models.accion_agente import AccionAgente
from app.models.diagrama import Diagrama
from app.models.mensaje_proyecto import MensajeProyecto
from app.models.proyecto import Proyecto
from app.models.usuario import Usuario
from app.realtime import (
    documentos,
    emitir_contenido,
    emitir_mensaje,
    emitir_mensaje_actualizado,
    historial,
    nombre_en_sala,
    revisor,
)
from app.schemas.mensaje_proyecto import MensajeOut
from app.services.comando_voz import ComandoNoInterpretadoError, aplicar_accion, buscar_clase
from app.services.constantes_diagrama import (
    TIPOS_DATO,
    TIPOS_RELACION,
    VISIBILIDADES,
    multiplicidad_valida,
    normalizar,
    tipo_dato_canonico,
)
from app.services.documento_vivo import (
    huella_sin_posiciones,
    normalizar_contenido,
    restaurar_con_posiciones_actuales,
)

logger = logging.getLogger(__name__)

MAX_OPERACIONES = 30
MAX_LARGO_NOMBRE = 100
MAX_LARGO_JUSTIFICACION = 300

_ETIQUETA_RELACION = {
    "asociacion": "asociación",
    "herencia": "herencia",
    "agregacion": "agregación",
    "composicion": "composición",
    "dependencia": "dependencia",
    "realizacion": "realización",
}


class OperacionRechazada(Exception):
    """Un pedido que no se puede aplicar. El mensaje se muestra tal cual en el chat."""


class AccionNoPermitida(Exception):
    """Un botón que ya no corresponde. El mensaje se muestra junto al botón."""

    def __init__(self, status: int, detalle: str):
        super().__init__(detalle)
        self.status = status
        self.detalle = detalle


_candados: dict[int, asyncio.Lock] = {}


def _candado(proyecto_id: int) -> asyncio.Lock:
    """Un pedido por vez en cada proyecto, para que un doble clic no aplique dos veces.
    No se tiene tomado mientras se espera a la IA."""
    return _candados.setdefault(proyecto_id, asyncio.Lock())


# ---- Validación ----


def _nombre_valido(nombre, etiqueta: str) -> str:
    texto = nombre.strip() if isinstance(nombre, str) else ""
    if not texto or len(texto) > MAX_LARGO_NOMBRE:
        raise OperacionRechazada(f"El nombre de {etiqueta} no es válido.")
    return texto


def _tipo_valido(tipo) -> str | None:
    if tipo is None or tipo == "":
        return None
    canonico = tipo_dato_canonico(tipo)
    if canonico is None:
        raise OperacionRechazada(
            f'El tipo de dato "{tipo}" no es válido. Los tipos son: {", ".join(TIPOS_DATO)}. '
            "Para vincular con otra clase, usá una relación."
        )
    return canonico


def _visibilidad_valida(visibilidad) -> None:
    if visibilidad is not None and visibilidad not in VISIBILIDADES:
        raise OperacionRechazada(f'La visibilidad "{visibilidad}" no es válida.')


def _validar_item(item: dict, campo: str, *, parcial: bool) -> dict:
    etiqueta = "atributo" if campo == "atributos" else "método"
    item = dict(item)
    if not parcial or item.get("nombre") is not None:
        item["nombre"] = _nombre_valido(item.get("nombre"), f"un {etiqueta}")
    _visibilidad_valida(item.get("visibilidad"))
    if campo == "atributos":
        item["tipo"] = _tipo_valido(item.get("tipo"))
        # Todo atributo nuevo lleva tipo: String es también el valor por defecto del generador.
        if item["tipo"] is None and not parcial:
            item["tipo"] = "String"
    return item


def _validar_campos_relacion(datos: dict) -> None:
    tipo = datos.get("tipo")
    if tipo is not None and tipo not in TIPOS_RELACION:
        raise OperacionRechazada(f'El tipo de relación "{tipo}" no es válido.')
    for clave in ("multiplicidadOrigen", "multiplicidadDestino"):
        valor = datos.get(clave)
        if valor is not None and not multiplicidad_valida(valor):
            raise OperacionRechazada(f'La multiplicidad "{valor}" no es válida.')


def _validar_operacion(accion: dict) -> dict:
    """Valida los argumentos antes de aplicar. Devuelve una copia con los tipos de dato
    y los nombres ya normalizados."""
    tipo = accion.get("accion")
    accion = dict(accion)

    if tipo == "crear_clase":
        accion["clase"] = _nombre_valido(accion.get("clase"), "la clase")
    if tipo == "renombrar_clase":
        accion["nombre_nuevo"] = _nombre_valido(accion.get("nombre_nuevo"), "la clase")

    parcial = tipo in ("editar_atributo", "editar_metodo")
    for campo in ("atributos", "metodos"):
        if accion.get(campo):
            accion[campo] = [_validar_item(i, campo, parcial=parcial) for i in accion[campo]]

    if accion.get("relacion"):
        _validar_campos_relacion(accion["relacion"])
    if tipo == "crear_relacion":
        rel = accion["relacion"]
        if buscar_clase([{"data": {"nombre": rel.get("claseOrigen")}}], rel.get("claseDestino")):
            raise OperacionRechazada("Una relación tiene que ser entre dos clases distintas.")
    if accion.get("cambios_relacion"):
        _validar_campos_relacion(accion["cambios_relacion"])
    return accion


def _rechazar_repetido(contenido: dict, accion: dict) -> None:
    """El editor y la voz permiten repetir nombres; a pedido del agente es casi seguro
    un error de interpretación, y el resultado no se podría generar."""
    tipo = accion.get("accion")
    if tipo not in ("agregar_atributo", "agregar_metodo"):
        return
    campo = "atributos" if tipo == "agregar_atributo" else "metodos"
    nodo = buscar_clase(contenido["nodes"], accion.get("clase"))
    if nodo is None:
        return
    existentes = {(i.get("texto") or "").lower() for i in (nodo.get("data") or {}).get(campo) or []}
    for item in accion.get(campo) or []:
        if item["nombre"].lower() in existentes:
            etiqueta = "atributo" if campo == "atributos" else "método"
            raise OperacionRechazada(f'La clase "{nodo["data"]["nombre"]}" ya tiene un {etiqueta} "{item["nombre"]}".')


def _clase_referida(nombre_atributo: str, clases: dict[str, str]) -> str | None:
    """La clase que representa un atributo: `autor`, `autores`, `idAutor`, `autor_id`,
    `fkAutor`. `clases` va de nombre normalizado a nombre real."""
    nombre = normalizar(nombre_atributo).replace("_", "")
    candidatos = {nombre}
    for prefijo in ("id", "fk"):
        if nombre.startswith(prefijo):
            candidatos.add(nombre[len(prefijo):])
        if nombre.endswith(prefijo):
            candidatos.add(nombre[: -len(prefijo)])
    for candidato in list(candidatos):
        for plural in ("es", "s"):
            if candidato.endswith(plural):
                candidatos.add(candidato[: -len(plural)])
    return next((clases[c] for c in candidatos if c in clases), None)


def _hay_relacion(contenido: dict, operaciones: list[dict], clase_a: str, clase_b: str) -> bool:
    par = {normalizar(clase_a), normalizar(clase_b)}
    for accion in operaciones:
        rel = accion.get("relacion") or {}
        if accion.get("accion") == "crear_relacion" and {normalizar(rel.get("claseOrigen")), normalizar(rel.get("claseDestino"))} == par:
            return True
    nombres = {n["id"]: normalizar((n.get("data") or {}).get("nombre")) for n in contenido["nodes"]}
    return any({nombres.get(e.get("source")), nombres.get(e.get("target"))} == par for e in contenido["edges"])


def _sin_atributos_de_otra_clase(contenido: dict, operaciones: list[dict]) -> list[dict]:
    """Un atributo que representa a otra clase (`autor`, `idVenta`) es una clave foránea
    escrita a mano y duplica la relación. Si la relación está, se descarta avisando; si no,
    se rechaza el pedido. Es control por código porque el prompt solo no alcanzó."""
    clases = {normalizar((n.get("data") or {}).get("nombre")): n["data"]["nombre"] for n in contenido["nodes"]}
    for accion in operaciones:
        if accion.get("accion") == "crear_clase":
            clases[normalizar(accion.get("clase"))] = accion.get("clase")

    resultado = []
    for accion in operaciones:
        if accion.get("accion") not in ("crear_clase", "agregar_atributo", "editar_atributo"):
            resultado.append(accion)
            continue
        duena = accion.get("clase")
        conservados, omitidos = [], []
        for item in accion.get("atributos") or []:
            referida = _clase_referida(item.get("nombre") or "", clases)
            if referida is None or normalizar(referida) == normalizar(duena):
                conservados.append(item)
            elif _hay_relacion(contenido, operaciones, duena, referida):
                omitidos.append(item["nombre"])
            else:
                raise OperacionRechazada(
                    f'El atributo "{item["nombre"]}" representa a la clase {referida}: eso va como una '
                    f"relación, no como un atributo. Pedime que relacione {duena} con {referida}."
                )
        if omitidos and not conservados and accion["accion"] != "crear_clase":
            if len(operaciones) == 1:
                raise OperacionRechazada(
                    f'El atributo "{omitidos[0]}" no hace falta: la relación con esa clase ya lo representa.'
                )
            continue
        resultado.append({**accion, "atributos": conservados, "atributos_omitidos": omitidos} if omitidos else accion)
    return resultado


def _sin_relaciones_repetidas(operaciones: list[dict]) -> list[dict]:
    """El modelo a veces crea la misma relación una vez por cada sentido."""
    vistas = set()
    resultado = []
    for accion in operaciones:
        rel = accion.get("relacion") or {}
        if accion.get("accion") == "crear_relacion":
            clave = (
                frozenset({normalizar(rel.get("claseOrigen")), normalizar(rel.get("claseDestino"))}),
                rel.get("tipo") or "asociacion",
            )
            if clave in vistas:
                continue
            vistas.add(clave)
        resultado.append(accion)
    return resultado


def _depurar(contenido: dict, operaciones: list[dict]) -> list[dict]:
    """Lo que se aplica y lo que dice el resumen tienen que ser exactamente lo mismo."""
    return _sin_atributos_de_otra_clase(contenido, _sin_relaciones_repetidas(operaciones))


def _con_cercania(operaciones: list[dict]) -> list[dict]:
    """Una clase nueva va junto a la clase con la que se relaciona en este mismo pedido."""
    resultado = []
    for accion in operaciones:
        if accion.get("accion") == "crear_clase" and not accion.get("cerca_de"):
            nombre = (accion.get("clase") or "").lower()
            for otra in operaciones:
                rel = otra.get("relacion") if otra.get("accion") == "crear_relacion" else None
                if not rel:
                    continue
                origen, destino = rel.get("claseOrigen") or "", rel.get("claseDestino") or ""
                if origen.lower() == nombre:
                    accion = {**accion, "cerca_de": destino}
                    break
                if destino.lower() == nombre:
                    accion = {**accion, "cerca_de": origen}
                    break
        resultado.append(accion)
    return resultado


def probar_operaciones(contenido: dict, operaciones: list[dict]) -> dict:
    """Aplica todo sobre una copia y devuelve el resultado. Función pura: si algo falla
    lanza OperacionRechazada, y `contenido` queda intacto."""
    if not operaciones:
        raise OperacionRechazada("No entendí qué hay que cambiar.")
    if len(operaciones) > MAX_OPERACIONES:
        raise OperacionRechazada(f"Es demasiado para un solo pedido (máximo {MAX_OPERACIONES} cambios).")

    depuradas = _depurar(contenido, operaciones)
    if not depuradas:
        raise OperacionRechazada("Esos atributos no hacen falta: las relaciones ya los representan.")

    resultado = contenido
    for accion in _con_cercania(depuradas):
        accion = _validar_operacion(accion)
        _rechazar_repetido(resultado, accion)
        try:
            resultado = aplicar_accion(resultado, accion)
        except ComandoNoInterpretadoError as exc:
            raise OperacionRechazada(str(exc)) from exc
        except (KeyError, TypeError, AttributeError, IndexError) as exc:
            raise OperacionRechazada("No pude interpretar uno de los cambios.") from exc
    return normalizar_contenido(resultado)


def _nombres_de_clases(accion: dict) -> list[str]:
    rel = accion.get("relacion") or {}
    return [n for n in (accion.get("clase"), rel.get("claseOrigen"), rel.get("claseDestino")) if n]


def _clases_afectadas(contenido: dict, operaciones: list[dict]) -> set[str]:
    """Las clases ya existentes que toca el pedido, incluidos los extremos de una relación."""
    ids = set()
    for accion in operaciones:
        for nombre in _nombres_de_clases(accion):
            nodo = buscar_clase(contenido["nodes"], nombre)
            if nodo is not None:
                ids.add(nodo["id"])
    return ids


def _rechazar_si_en_uso(proyecto_id: int, diagrama_id: int, contenido: dict, operaciones: list, solicitante: int):
    en_uso = revisor.quien_edita(proyecto_id, _clases_afectadas(contenido, operaciones), excepto=solicitante)
    if en_uso is None:
        return
    clase_id, usuario_id = en_uso
    clase = next(n for n in contenido["nodes"] if n["id"] == clase_id)["data"]["nombre"]
    quien = nombre_en_sala(diagrama_id, usuario_id) or "otro integrante"
    raise OperacionRechazada(f'"{clase}" está en uso por {quien}. Probá de nuevo cuando la suelte.')


# ---- Resúmenes ----


def _con_multiplicidad(clase: str | None, multiplicidad: str | None) -> str:
    return f"{clase} ({multiplicidad})" if multiplicidad else f"{clase}"


def describir_operacion(accion: dict) -> str:
    tipo, clase = accion.get("accion"), accion.get("clase")
    rel = accion.get("relacion") or {}
    entre = f'{rel.get("claseOrigen")} y {rel.get("claseDestino")}'
    if tipo == "crear_clase":
        return f"Creé la clase {clase}."
    if tipo == "renombrar_clase":
        return f'Renombré {clase} a {accion.get("nombre_nuevo")}.'
    if tipo == "eliminar_clase":
        return f"Eliminé la clase {clase}."
    if tipo in ("agregar_atributo", "agregar_metodo"):
        campo, etiqueta = ("atributos", "atributo") if tipo == "agregar_atributo" else ("metodos", "método")
        nombres = ", ".join(i["nombre"] for i in accion.get(campo) or [])
        return f"Agregué el {etiqueta} {nombres} a {clase}."
    if tipo in ("editar_atributo", "editar_metodo"):
        etiqueta = "atributo" if tipo == "editar_atributo" else "método"
        return f'Modifiqué el {etiqueta} {accion.get("elemento_objetivo")} de {clase}.'
    if tipo in ("eliminar_atributo", "eliminar_metodo"):
        etiqueta = "atributo" if tipo == "eliminar_atributo" else "método"
        return f'Eliminé el {etiqueta} {accion.get("elemento_objetivo")} de {clase}.'
    if tipo == "crear_relacion":
        etiqueta = _ETIQUETA_RELACION.get(rel.get("tipo") or "asociacion", "relación")
        origen = _con_multiplicidad(rel.get("claseOrigen"), rel.get("multiplicidadOrigen"))
        destino = _con_multiplicidad(rel.get("claseDestino"), rel.get("multiplicidadDestino"))
        justificacion = (accion.get("justificacion") or "").strip()[:MAX_LARGO_JUSTIFICACION]
        return f"Creé una {etiqueta} entre {origen} y {destino}." + (f" {justificacion}" if justificacion else "")
    if tipo == "editar_relacion":
        return f"Modifiqué la relación entre {entre}."
    if tipo == "eliminar_relacion":
        return f"Eliminé la relación entre {entre}."
    return "Apliqué un cambio."


_INFINITIVOS = {
    "Creé": "crear",
    "Renombré": "renombrar",
    "Eliminé": "eliminar",
    "Agregué": "agregar",
    "Modifiqué": "modificar",
    "Apliqué": "aplicar",
}


def _en_infinitivo(descripcion: str) -> str:
    verbo, resto = descripcion.split(" ", 1)
    return f"{_INFINITIVOS.get(verbo, verbo)} {resto}"


def _resumen(contenido: dict, operaciones: list[dict]) -> str:
    lineas = []
    for accion in _depurar(contenido, operaciones):
        lineas.append(f"- {describir_operacion(accion)}")
        for nombre in accion.get("atributos_omitidos") or []:
            lineas.append(f"- No agregué el atributo {nombre}: esa información ya la da la relación.")
    return "\n".join(lineas)


def _clase_principal(antes: dict, despues: dict, operaciones: list[dict]) -> str | None:
    for accion in operaciones:
        # Una clase renombrada se busca por su nombre nuevo; una borrada, en lo de antes.
        for nombre in [accion.get("nombre_nuevo"), *_nombres_de_clases(accion)]:
            nodo = buscar_clase(despues["nodes"], nombre) or buscar_clase(antes["nodes"], nombre)
            if nodo is not None:
                return nodo["id"]
    return None


# ---- Persistencia (en hilos aparte: la base es síncrona) ----


def _leer_diagrama(proyecto_id: int) -> tuple[int, dict] | None:
    with SessionLocal() as db:
        diagrama = db.query(Diagrama).filter(Diagrama.id_proyecto == proyecto_id).first()
        if diagrama is None:
            return None
        return diagrama.id, diagrama.contenido or {}


async def _estado_actual(proyecto_id: int) -> tuple[int, dict]:
    leido = await asyncio.to_thread(_leer_diagrama, proyecto_id)
    if leido is None:
        raise OperacionRechazada("Este proyecto todavía no tiene diagrama.")
    diagrama_id, de_la_base = leido
    return diagrama_id, documentos.obtener(proyecto_id) or normalizar_contenido(de_la_base)


def _guardar_mensaje(
    proyecto_id: int, tipo: str, texto: str, destino: int | None = None
) -> MensajeOut:
    with SessionLocal() as db:
        mensaje = MensajeProyecto(id_proyecto=proyecto_id, tipo=tipo, texto=texto, id_usuario_destino=destino)
        db.add(mensaje)
        db.commit()
        db.refresh(mensaje)
        return MensajeOut.desde_modelo(mensaje)


async def publicar_mensaje(proyecto_id: int, tipo: str, texto: str, destino: int | None = None) -> None:
    salida = await asyncio.to_thread(_guardar_mensaje, proyecto_id, tipo, texto, destino)
    await emitir_mensaje(salida)


def _guardar_aplicacion(
    proyecto_id: int,
    diagrama_id: int,
    contenido: dict,
    copia: dict,
    operaciones: list[dict],
    id_solicitante: int,
    id_sugerencia: int | None,
    clase_principal: str | None,
) -> tuple[MensajeOut, MensajeOut | None]:
    """El diagrama, la acción y el mensaje en una sola transacción. Se guarda la versión
    viva, que puede ya incluir ediciones hechas después de aplicar."""
    with SessionLocal() as db:
        diagrama = db.get(Diagrama, diagrama_id)
        diagrama.contenido = documentos.obtener(proyecto_id) or contenido
        mensaje = MensajeProyecto(
            id_proyecto=proyecto_id,
            tipo="agente",
            texto=_resumen(copia, operaciones),
            id_usuario_destino=id_solicitante,
            elemento_referenciado=clase_principal,
        )
        db.add(mensaje)
        db.flush()
        db.add(
            AccionAgente(
                id_proyecto=proyecto_id,
                id_solicitante=id_solicitante,
                id_mensaje=mensaje.id,
                id_sugerencia=id_sugerencia,
                estado="aplicada",
                operaciones=operaciones,
                copia_contenido=copia,
                huella_resultante=huella_sin_posiciones(contenido),
            )
        )
        db.commit()
        salida = MensajeOut.desde_modelo(db.get(MensajeProyecto, mensaje.id))
        sugerencia = db.get(MensajeProyecto, id_sugerencia) if id_sugerencia else None
        return salida, MensajeOut.desde_modelo(sugerencia) if sugerencia else None


def _guardar_pendiente(
    proyecto_id: int, operaciones: list[dict], id_solicitante: int, id_sugerencia: int | None,
    texto: str, clase_principal: str | None,
) -> MensajeOut:
    with SessionLocal() as db:
        mensaje = MensajeProyecto(
            id_proyecto=proyecto_id,
            tipo="agente",
            texto=texto,
            id_usuario_destino=id_solicitante,
            elemento_referenciado=clase_principal,
        )
        db.add(mensaje)
        db.flush()
        db.add(
            AccionAgente(
                id_proyecto=proyecto_id,
                id_solicitante=id_solicitante,
                id_mensaje=mensaje.id,
                id_sugerencia=id_sugerencia,
                estado="pendiente",
                operaciones=operaciones,
            )
        )
        db.commit()
        return MensajeOut.desde_modelo(db.get(MensajeProyecto, mensaje.id))


def _leer_accion(proyecto_id: int, accion_id: int) -> dict | None:
    with SessionLocal() as db:
        accion = db.get(AccionAgente, accion_id)
        if accion is None or accion.id_proyecto != proyecto_id:
            return None
        return {
            "estado": accion.estado,
            "id_solicitante": accion.id_solicitante,
            "id_sugerencia": accion.id_sugerencia,
            "operaciones": accion.operaciones,
            "copia_contenido": accion.copia_contenido,
            "huella_resultante": accion.huella_resultante,
        }


def _guardar_estado(accion_id: int, estado: str) -> tuple[MensajeOut | None, MensajeOut | None]:
    """Devuelve el mensaje de la acción y su sugerencia, para actualizarlos en los clientes."""
    with SessionLocal() as db:
        accion = db.get(AccionAgente, accion_id)
        accion.estado = estado
        id_mensaje, id_sugerencia = accion.id_mensaje, accion.id_sugerencia
        db.commit()
        mensaje = db.get(MensajeProyecto, id_mensaje) if id_mensaje else None
        sugerencia = db.get(MensajeProyecto, id_sugerencia) if id_sugerencia else None
        return (
            MensajeOut.desde_modelo(mensaje) if mensaje else None,
            MensajeOut.desde_modelo(sugerencia) if sugerencia else None,
        )


def _guardar_deshacer(proyecto_id: int, diagrama_id: int, contenido: dict, accion_id: int, nombre: str):
    with SessionLocal() as db:
        diagrama = db.get(Diagrama, diagrama_id)
        diagrama.contenido = documentos.obtener(proyecto_id) or contenido
        accion = db.get(AccionAgente, accion_id)
        accion.estado = "deshecha"
        aviso = MensajeProyecto(
            id_proyecto=proyecto_id, tipo="sistema", texto=f"{nombre} deshizo los cambios del agente."
        )
        db.add(aviso)
        id_mensaje, id_sugerencia = accion.id_mensaje, accion.id_sugerencia
        db.commit()
        mensaje = db.get(MensajeProyecto, id_mensaje)
        sugerencia = db.get(MensajeProyecto, id_sugerencia) if id_sugerencia else None
        return (
            MensajeOut.desde_modelo(aviso),
            MensajeOut.desde_modelo(mensaje),
            MensajeOut.desde_modelo(sugerencia) if sugerencia else None,
        )


def _es_miembro(proyecto_id: int, usuario_id: int) -> bool:
    with SessionLocal() as db:
        proyecto, usuario = db.get(Proyecto, proyecto_id), db.get(Usuario, usuario_id)
        return bool(proyecto and usuario and rol_de_usuario_en_proyecto(proyecto, usuario, db))


# ---- Aplicación ----


async def aplicar_operaciones(
    proyecto_id: int,
    operaciones: list[dict],
    id_solicitante: int,
    id_sugerencia: int | None = None,
) -> None:
    """Punto único por el que el agente modifica un diagrama. CU18 se engancha acá: cada
    aplicación queda en `acciones_agente`, con quién la pidió y qué se hizo.

    Se llama con el candado del proyecto tomado. Lanza OperacionRechazada si no se puede
    aplicar, sin haber cambiado nada.
    """
    diagrama_id, _ = await _estado_actual(proyecto_id)
    if not await asyncio.to_thread(_es_miembro, proyecto_id, id_solicitante):
        raise OperacionRechazada("Quien hizo el pedido ya no es miembro del proyecto.")

    # Sin `await` de acá a `reemplazar`: ningún mensaje de un cliente puede intercalarse.
    antes = documentos.obtener(proyecto_id) or (await _estado_actual(proyecto_id))[1]
    _rechazar_si_en_uso(proyecto_id, diagrama_id, antes, operaciones, id_solicitante)
    despues = probar_operaciones(antes, operaciones)
    cambios = documentos.reemplazar(proyecto_id, despues)
    # Sin pasar por el revisor como edición: los cambios del agente no generan sugerencias.
    revisor.sincronizar(proyecto_id, despues)

    try:
        salida, sugerencia = await asyncio.to_thread(
            _guardar_aplicacion,
            proyecto_id,
            diagrama_id,
            despues,
            antes,
            operaciones,
            id_solicitante,
            id_sugerencia,
            _clase_principal(antes, despues, operaciones),
        )
    except Exception:
        # Si ya hubo ediciones encima, deshacer el documento vivo también las borraría.
        vivo = documentos.obtener(proyecto_id)
        if vivo is not None and huella_sin_posiciones(vivo) == huella_sin_posiciones(despues):
            documentos.reemplazar(proyecto_id, antes)
            revisor.sincronizar(proyecto_id, antes)
        raise

    # Recién acá: si no se pudo guardar, el cambio se revirtió y no pasó.
    historial.registrar_operacion(proyecto_id, id_solicitante, "agente", antes, despues, por_agente=True)

    await emitir_contenido(diagrama_id, despues, cambios)
    await emitir_mensaje(salida)
    if sugerencia is not None:
        await emitir_mensaje_actualizado(sugerencia)


async def ejecutar_pedido(
    proyecto_id: int, operaciones: list[dict], id_solicitante: int, id_sugerencia: int | None = None
) -> None:
    """Atiende un pedido ya interpretado. Si no se puede aplicar, lo explica en el chat."""
    async with _candado(proyecto_id):
        try:
            if any(a.get("accion") == "eliminar_clase" for a in operaciones):
                await _pedir_confirmacion(proyecto_id, operaciones, id_solicitante, id_sugerencia)
            else:
                await aplicar_operaciones(proyecto_id, operaciones, id_solicitante, id_sugerencia)
        except OperacionRechazada as exc:
            await publicar_mensaje(proyecto_id, "agente", f"No apliqué ningún cambio. {exc}", destino=id_solicitante)


async def _pedir_confirmacion(
    proyecto_id: int, operaciones: list[dict], id_solicitante: int, id_sugerencia: int | None
) -> None:
    """Eliminar una clase espera confirmación. Se valida ya, para no ofrecer confirmar
    algo que de entrada no se puede hacer; al confirmar se vuelve a validar."""
    diagrama_id, contenido = await _estado_actual(proyecto_id)
    _rechazar_si_en_uso(proyecto_id, diagrama_id, contenido, operaciones, id_solicitante)
    despues = probar_operaciones(contenido, operaciones)

    eliminadas = [a["clase"] for a in operaciones if a.get("accion") == "eliminar_clase"]
    otras = [a for a in _depurar(contenido, operaciones) if a.get("accion") != "eliminar_clase"]
    texto = f"¿Confirmás que elimine {', '.join(eliminadas)} con todas sus relaciones?"
    if otras:
        texto += "\nTambién voy a:\n" + "\n".join(f"- {_en_infinitivo(describir_operacion(a))}" for a in otras)
    salida = await asyncio.to_thread(
        _guardar_pendiente,
        proyecto_id,
        operaciones,
        id_solicitante,
        id_sugerencia,
        texto,
        _clase_principal(contenido, despues, operaciones),
    )
    await emitir_mensaje(salida)


async def _accion_de(proyecto_id: int, accion_id: int, usuario_id: int, estado: str) -> dict:
    accion = await asyncio.to_thread(_leer_accion, proyecto_id, accion_id)
    if accion is None:
        raise AccionNoPermitida(404, "Esa acción no existe.")
    if accion["id_solicitante"] != usuario_id:
        raise AccionNoPermitida(403, "Solo puede hacerlo quien pidió el cambio.")
    if accion["estado"] != estado:
        raise AccionNoPermitida(409, "Esta acción ya se resolvió.")
    return accion


async def confirmar(proyecto_id: int, accion_id: int, usuario_id: int) -> None:
    async with _candado(proyecto_id):
        accion = await _accion_de(proyecto_id, accion_id, usuario_id, "pendiente")
        try:
            await aplicar_operaciones(proyecto_id, accion["operaciones"], usuario_id, accion["id_sugerencia"])
        except OperacionRechazada as exc:
            # Sigue pendiente: si la clase estaba en uso, se puede confirmar más tarde.
            raise AccionNoPermitida(409, str(exc)) from exc
        mensaje, _ = await asyncio.to_thread(_guardar_estado, accion_id, "confirmada")
        if mensaje is not None:
            await emitir_mensaje_actualizado(mensaje)


async def cancelar(proyecto_id: int, accion_id: int, usuario_id: int) -> None:
    async with _candado(proyecto_id):
        await _accion_de(proyecto_id, accion_id, usuario_id, "pendiente")
        mensaje, _ = await asyncio.to_thread(_guardar_estado, accion_id, "cancelada")
        if mensaje is not None:
            await emitir_mensaje_actualizado(mensaje)


async def deshacer(proyecto_id: int, accion_id: int, usuario_id: int, nombre: str) -> None:
    """Restaura la copia, solo si nada cambió desde entonces salvo la posición de las
    clases, que se conserva."""
    async with _candado(proyecto_id):
        accion = await _accion_de(proyecto_id, accion_id, usuario_id, "aplicada")
        diagrama_id, _ = await _estado_actual(proyecto_id)

        actual = documentos.obtener(proyecto_id) or (await _estado_actual(proyecto_id))[1]
        if huella_sin_posiciones(actual) != accion["huella_resultante"]:
            raise AccionNoPermitida(409, "No se puede deshacer: el diagrama cambió después de este cambio.")
        restaurado = restaurar_con_posiciones_actuales(normalizar_contenido(accion["copia_contenido"]), actual)
        cambios = documentos.reemplazar(proyecto_id, restaurado)
        revisor.sincronizar(proyecto_id, restaurado)

        try:
            aviso, mensaje, sugerencia = await asyncio.to_thread(
                _guardar_deshacer, proyecto_id, diagrama_id, restaurado, accion_id, nombre
            )
        except Exception:
            vivo = documentos.obtener(proyecto_id)
            if vivo is not None and huella_sin_posiciones(vivo) == huella_sin_posiciones(restaurado):
                documentos.reemplazar(proyecto_id, actual)
                revisor.sincronizar(proyecto_id, actual)
            raise

        historial.registrar_operacion(proyecto_id, usuario_id, "deshacer", actual, restaurado)

        await emitir_contenido(diagrama_id, restaurado, cambios)
        await emitir_mensaje(aviso)
        await emitir_mensaje_actualizado(mensaje)
        if sugerencia is not None:
            await emitir_mensaje_actualizado(sugerencia)
