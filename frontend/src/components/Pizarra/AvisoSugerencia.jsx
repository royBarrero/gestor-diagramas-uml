import { useState } from 'react'
import { useStore, useViewport } from '@xyflow/react'
import MensajeFormateado from '../Asistente/MensajeFormateado'
import styles from './AvisoSugerencia.module.css'

const ANCHO_AVISO = 360
const ALTO_ESTIMADO = 200
const MARGEN = 12
const ANCHO_NODO_POR_DEFECTO = 240

// CU16: aviso junto a la clase, solo para quien hizo el cambio. Va fuera de
// canvasRef para no salir en el PNG, así que sigue a mano el zoom y el
// desplazamiento del lienzo.
function AvisoSugerencia({ aviso, nodo, onVerEnChat, onIgnorar, onPausar, onPedirCorreccion }) {
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
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

  async function handlePedirCorreccion() {
    setEnviando(true)
    setError(null)
    setError(await onPedirCorreccion())
    setEnviando(false)
  }

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
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <div className={styles.acciones}>
        <button type="button" className={styles.botonSecundario} onClick={onIgnorar}>
          Ignorar
        </button>
        <button type="button" className={styles.botonSecundario} onClick={onVerEnChat}>
          Ver en chat
        </button>
        <button type="button" className={styles.botonPrincipal} disabled={enviando} onClick={handlePedirCorreccion}>
          Pedir corrección
        </button>
      </div>
    </aside>
  )
}

export default AvisoSugerencia
