// Deshacer/rehacer de la pizarra. Cada entrada del historial guarda solo las
// clases y relaciones que tocó una acción (por id, con su versión antes y
// después), no una foto entera del diagrama: así deshacer no pisa lo que un
// colaborador cambió mientras tanto en otras clases.

// Estado visual de React Flow: que cambie no es una edición del diagrama.
const CLAVES_VISUALES = new Set(['selected', 'dragging', 'measured', 'resizing'])

function sinEstadoVisual(elemento) {
  return Object.fromEntries(Object.entries(elemento).filter(([clave]) => !CLAVES_VISUALES.has(clave)))
}

function iguales(a, b) {
  if (a === b) return true
  if (!a || !b) return false
  return JSON.stringify(sinEstadoVisual(a)) === JSON.stringify(sinEstadoVisual(b))
}

function diffLista(antes, despues) {
  const porIdAntes = new Map(antes.map((e) => [e.id, e]))
  const porIdDespues = new Map(despues.map((e) => [e.id, e]))
  const cambios = []
  for (const [id, previo] of porIdAntes) {
    const actual = porIdDespues.get(id) ?? null
    if (!iguales(previo, actual)) cambios.push({ id, antes: previo, despues: actual })
  }
  for (const [id, actual] of porIdDespues) {
    if (!porIdAntes.has(id)) cambios.push({ id, antes: null, despues: actual })
  }
  return cambios
}

export function calcularDiff(nodesAntes, edgesAntes, nodesDespues, edgesDespues) {
  return { nodes: diffLista(nodesAntes, nodesDespues), edges: diffLista(edgesAntes, edgesDespues) }
}

export function diffVacio(diff) {
  return diff.nodes.length === 0 && diff.edges.length === 0
}

// Acumula `posterior` sobre `anterior` (misma acción continuada, ej. escribir
// letra por letra): conserva el `antes` original y toma el `despues` más nuevo.
function fusionarLista(anterior, posterior) {
  const porId = new Map(anterior.map((c) => [c.id, c]))
  for (const cambio of posterior) {
    const previo = porId.get(cambio.id)
    porId.set(cambio.id, previo ? { ...previo, despues: cambio.despues } : cambio)
  }
  return [...porId.values()].filter((c) => !iguales(c.antes, c.despues))
}

export function fusionarDiffs(anterior, posterior) {
  return {
    nodes: fusionarLista(anterior.nodes, posterior.nodes),
    edges: fusionarLista(anterior.edges, posterior.edges),
  }
}

// Si se borra una clase que era clase de asociación de alguna relación, la
// relación se conserva pero pierde la referencia (si no, quedaría apuntando a un
// nodo inexistente en el contenido guardado).
export function quitarClasesAsociacion(eds, idsBorrados) {
  return eds.map((e) =>
    idsBorrados.includes(e.data?.claseAsociacion) ? { ...e, data: { ...e.data, claseAsociacion: null } } : e
  )
}

function aplicarLista(actual, cambios, lado) {
  const resultado = [...actual]
  for (const cambio of cambios) {
    const valor = cambio[lado]
    const indice = resultado.findIndex((e) => e.id === cambio.id)
    if (valor === null) {
      if (indice !== -1) resultado.splice(indice, 1)
    } else if (indice !== -1) {
      resultado[indice] = { ...valor, selected: false }
    } else {
      resultado.push({ ...valor, selected: false })
    }
  }
  return resultado
}

// Aplica un lado ('antes' para deshacer, 'despues' para rehacer) sobre el
// estado actual. Descarta relaciones que quedaron sin alguno de sus extremos
// y referencias a clases de asociación que ya no existen.
export function aplicarLado(nodes, edges, diff, lado) {
  const nuevosNodes = aplicarLista(nodes, diff.nodes, lado)
  const ids = new Set(nuevosNodes.map((n) => n.id))
  const edgesValidos = aplicarLista(edges, diff.edges, lado).filter((e) => ids.has(e.source) && ids.has(e.target))
  const idsInexistentes = edgesValidos.map((e) => e.data?.claseAsociacion).filter((id) => id && !ids.has(id))
  return { nodes: nuevosNodes, edges: quitarClasesAsociacion(edgesValidos, idsInexistentes) }
}
