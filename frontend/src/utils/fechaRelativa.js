const formateador = new Intl.RelativeTimeFormat('es', { numeric: 'auto' })
// Solo los minutos van abreviados ("hace 12 min"); el resto completo ("hace 3 días").
const formateadorCorto = new Intl.RelativeTimeFormat('es', { numeric: 'auto', style: 'short' })

const UNIDADES = [
  ['year', 60 * 60 * 24 * 365],
  ['month', 60 * 60 * 24 * 30],
  ['week', 60 * 60 * 24 * 7],
  ['day', 60 * 60 * 24],
  ['hour', 60 * 60],
  ['minute', 60],
]

// "Hace 12 min", "Ayer", "Hace 3 días"... a partir de una fecha ISO.
export function fechaRelativa(fechaIso) {
  if (!fechaIso) return 'Sin cambios todavía'

  const segundos = (new Date(fechaIso).getTime() - Date.now()) / 1000
  const [unidad, duracion] = UNIDADES.find(([, d]) => Math.abs(segundos) >= d) ?? [null, null]
  if (!unidad) return 'Hace un momento'

  const texto = (unidad === 'minute' ? formateadorCorto : formateador).format(Math.round(segundos / duracion), unidad)
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}
