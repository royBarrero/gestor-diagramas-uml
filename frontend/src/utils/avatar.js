const COLORES_AVATAR = [
  { fondo: '#e5574a', texto: '#ffffff' },
  { fondo: '#34d399', texto: '#04291b' },
  { fondo: '#1f7ae0', texto: '#ffffff' },
  { fondo: '#a78bfa', texto: '#1e1240' },
  { fondo: '#f5a524', texto: '#2b1a00' },
]

// "Pepe González" -> "PG"; un solo nombre -> sus dos primeras letras.
export function iniciales(nombre) {
  const partes = (nombre ?? '').trim().split(/\s+/).filter(Boolean)
  if (partes.length === 0) return '?'
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase()
  return (partes[0][0] + partes[1][0]).toUpperCase()
}

// Color estable por usuario, derivado de su id.
export function colorAvatar(id) {
  return COLORES_AVATAR[Math.abs(Number(id) || 0) % COLORES_AVATAR.length]
}
