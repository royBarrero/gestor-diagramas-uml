import { useStore, useViewport } from '@xyflow/react'
import MensajeFormateado from '../Asistente/MensajeFormateado'
import styles from './AvisoSugerencia.module.css'

const ANCHO_AVISO = 300
const ALTO_ESTIMADO = 190
const MARGEN = 12
const ANCHO_NODO_POR_DEFECTO = 240

// CU16: aviso junto a la clase, solo para quien hizo el cambio. Va fuera de
// canvasRef para no salir en el PNG, así que sigue a mano el zoom y el
// desplazamiento del lienzo.
function AvisoSugerencia({ aviso, nodo, onVerEnChat, onIgnorar, onPausar }) {
  const { x, y, zoom } = useViewport()
  const anchoLienzo = useStore((estado) => estado.width)
  const altoLienzo = useStore((estado) => estado.height)

  const anchoNodo = nodo.measured?.width ?? ANCHO_NODO_POR_DEFECTO
  const izquierdaNodo = x + nodo.position.x * zoom
  const derechaNodo = izquierdaNodo + anchoNodo * zoom

  // A la derecha de la clase; si no entra, a la izquierda. Si la clase quedó
  // fuera de la vista, el aviso se mantiene dentro del lienzo.
  let left = derechaNodo + MARGEN
  if (left + ANCHO_AVISO > anchoLienzo - MARGEN) left = izquierdaNodo - ANCHO_AVISO - MARGEN
  left = Math.max(MARGEN, Math.min(left, anchoLienzo - ANCHO_AVISO - MARGEN))
  const top = Math.max(MARGEN, Math.min(y + nodo.position.y * zoom, altoLienzo - ALTO_ESTIMADO - MARGEN))

  return (
    <aside
      className={styles.aviso}
      style={{ left, top, width: ANCHO_AVISO }}
      role="status"
      aria-label={`Sugerencia de la IA sobre ${nodo.data.nombre}`}
      onMouseEnter={() => onPausar(true)}
      onMouseLeave={() => onPausar(false)}
      onFocus={() => onPausar(true)}
      onBlur={() => onPausar(false)}
    >
      <div className={styles.encabezado}>
        <i className="ti ti-sparkles" aria-hidden="true" />
        Sugerencia de la IA
      </div>
      <div className={styles.texto}>
        <MensajeFormateado texto={aviso.texto} />
      </div>
      <div className={styles.acciones}>
        <button type="button" className={styles.botonSecundario} onClick={onIgnorar}>
          Ignorar
        </button>
        <button type="button" className={styles.botonPrincipal} onClick={onVerEnChat}>
          Ver en chat
        </button>
      </div>
    </aside>
  )
}

export default AvisoSugerencia
