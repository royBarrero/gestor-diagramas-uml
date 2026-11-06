import { quitarClasesAsociacion } from './historialDiagrama'

// Lo que es de cada navegador y no define al diagrama. La selección y el arrastre
// no se difunden; `measured` sí viaja, para que React Flow no oculte la clase
// hasta volver a medirla, pero no cuenta como cambio.
const CAMPOS_NODO_LOCALES = ['selected', 'dragging']
const CAMPOS_NODO_MEDIDAS = ['measured', 'width', 'height']
const CAMPOS_EDGE_LOCALES = ['selected']
// Valor de la base que nunca coincide con la firma de un elemento.
const SIN_CONFIRMAR = 'sin-confirmar'

function sinCampos(objeto, campos) {
  const copia = { ...objeto }
  campos.forEach((campo) => delete copia[campo])
  return copia
}

// Con las claves ordenadas: PostgreSQL (JSONB) no conserva su orden.
function firma(valor) {
  return JSON.stringify(valor, (_clave, v) =>
    v && typeof v === 'object' && !Array.isArray(v)
      ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, v[k]]))
      : v
  )
}

const firmaNodo = (nodo) => firma(sinCampos(nodo, [...CAMPOS_NODO_LOCALES, ...CAMPOS_NODO_MEDIDAS]))
const firmaEdge = (edge) => firma(sinCampos(edge, CAMPOS_EDGE_LOCALES))

const firmasDeLista = (lista, firmar) => new Map((lista ?? []).map((e) => [e.id, firmar(e)]))

// La "base" es la última versión sincronizada de cada elemento, enviada o recibida.
export function firmasDe(nodes, edges) {
  return { nodes: firmasDeLista(nodes, firmaNodo), edges: firmasDeLista(edges, firmaEdge) }
}

function idsCambiados(base, actuales) {
  const ids = []
  actuales.forEach((valor, id) => {
    if (base.get(id) !== valor) ids.push(id)
  })
  base.forEach((_valor, id) => {
    if (!actuales.has(id)) ids.push(id)
  })
  return ids
}

// Lo que el usuario cambió respecto de la base; incluye lo que borró.
// Null si no hay nada que enviar.
export function calcularCambios(base, nodes, edges) {
  const actuales = firmasDe(nodes, edges)
  const cambios = {
    nodes: idsCambiados(base.nodes, actuales.nodes),
    edges: idsCambiados(base.edges, actuales.edges),
  }
  return cambios.nodes.length || cambios.edges.length ? { cambios, base: actuales } : null
}

// Un envío que el servidor no confirmó pudo perderse: sus elementos vuelven a
// contar como edición pendiente. Reenviarlo de más no hace daño.
export function marcarSinConfirmar(base, cambios) {
  cambios.nodes.forEach((id) => base.nodes.set(id, SIN_CONFIRMAR))
  cambios.edges.forEach((id) => base.edges.set(id, SIN_CONFIRMAR))
}

export function contenidoParaEnviar(nodes, edges, cambios) {
  return {
    nodes: nodes.map((nodo) => sinCampos(nodo, CAMPOS_NODO_LOCALES)),
    edges: edges.map((edge) => sinCampos(edge, CAMPOS_EDGE_LOCALES)),
    cambios,
  }
}

function fusionarLista(base, local, remoto, cambiados, firmar) {
  const localPorId = new Map(local.map((e) => [e.id, e]))
  const remotoPorId = new Map(remoto.map((e) => [e.id, e]))
  const nuevaBase = new Map(base)
  const elegidos = new Map()

  // Primero el orden local, para que las clases no cambien de capa; lo nuevo, al final.
  const ids = new Set([...localPorId.keys(), ...remotoPorId.keys(), ...base.keys()])
  ids.forEach((id) => {
    const enLocal = localPorId.get(id)
    const enRemoto = remotoPorId.get(id)
    const pendiente = (enLocal ? firmar(enLocal) : undefined) !== base.get(id)
    const lleva = !cambiados || cambiados.has(id)

    // Una edición pendiente no mueve la base, aunque lo recibido ya la contenga: la
    // recarga puede traerla porque se guardó por REST, y los demás igual no la vieron.
    if (pendiente || !lleva) {
      if (enLocal) elegidos.set(id, enLocal)
      return
    }
    if (enRemoto) {
      nuevaBase.set(id, firmar(enRemoto))
      // La selección es de cada usuario: el cambio ajeno no la quita.
      elegidos.set(id, enLocal?.selected ? { ...enRemoto, selected: true } : enRemoto)
    } else {
      nuevaBase.delete(id)
    }
  })

  return { lista: [...elegidos.values()], base: nuevaBase }
}

// Aplica un diagrama recibido sin perder lo que el usuario editó y todavía no
// envió. De cada clase y relación se toma lo recibido, salvo que tenga una edición
// local pendiente. Si el mensaje dice qué cambió quien lo envió (`cambios`), se
// aplica solo eso: el resto de su diagrama puede estar viejo si los dos enviaron
// casi a la vez. Sin `cambios` (endpoints, recarga al conectar) se toma todo.
export function fusionarRemoto(base, local, contenido) {
  const nodos = fusionarLista(
    base.nodes,
    local.nodes,
    contenido?.nodes ?? [],
    contenido?.cambios ? new Set(contenido.cambios.nodes) : null,
    firmaNodo
  )
  const relaciones = fusionarLista(
    base.edges,
    local.edges,
    contenido?.edges ?? [],
    contenido?.cambios ? new Set(contenido.cambios.edges) : null,
    firmaEdge
  )

  // Una clase pudo borrarse de un lado mientras del otro se le agregaba una relación.
  const idsNodos = new Set(nodos.lista.map((n) => n.id))
  const conExtremos = relaciones.lista.filter((e) => idsNodos.has(e.source) && idsNodos.has(e.target))
  const clasesAusentes = conExtremos
    .map((e) => e.data?.claseAsociacion)
    .filter((id) => id && !idsNodos.has(id))

  return {
    nodes: nodos.lista,
    edges: clasesAusentes.length ? quitarClasesAsociacion(conExtremos, clasesAusentes) : conExtremos,
    base: { nodes: nodos.base, edges: relaciones.base },
  }
}
