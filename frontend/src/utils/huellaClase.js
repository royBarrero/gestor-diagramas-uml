function itemsNormalizados(items) {
  return (items ?? []).map((i) => [i.visibilidad, i.tipo, i.texto].join('|')).sort()
}

// CU16: resume lo que define a una clase (nombre, atributos, métodos y
// relaciones) para saber si cambió. Moverla en el lienzo no cambia su huella.
export function huellaClase(nodes, edges, claseId) {
  const nodo = nodes.find((n) => n.id === claseId)
  if (!nodo) return null
  const relaciones = edges
    .filter((e) => e.source === claseId || e.target === claseId)
    .map((e) => [
      e.source,
      e.target,
      e.data?.tipo,
      e.data?.multiplicidadOrigen,
      e.data?.multiplicidadDestino,
      e.data?.nombre,
      e.data?.claseAsociacion,
    ].join('|'))
    .sort()
  return JSON.stringify([
    nodo.data?.nombre,
    itemsNormalizados(nodo.data?.atributos),
    itemsNormalizados(nodo.data?.metodos),
    relaciones,
  ])
}
