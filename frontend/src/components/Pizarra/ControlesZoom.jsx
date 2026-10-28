import { useReactFlow, useViewport } from '@xyflow/react'
import styles from './ControlesZoom.module.css'

function ControlesZoom() {
  const { zoomIn, zoomOut, fitView } = useReactFlow()
  const { zoom } = useViewport()

  return (
    <div className={styles.controles}>
      <button type="button" className={styles.boton} onClick={() => zoomOut({ duration: 200 })} title="Alejar">
        <i className="ti ti-minus" />
      </button>
      <span className={styles.porcentaje}>{Math.round(zoom * 100)}%</span>
      <button type="button" className={styles.boton} onClick={() => zoomIn({ duration: 200 })} title="Acercar">
        <i className="ti ti-plus" />
      </button>
      <span className={styles.separador} />
      <button type="button" className={styles.boton} onClick={() => fitView({ duration: 200 })} title="Ajustar a la pantalla">
        <i className="ti ti-maximize" />
      </button>
    </div>
  )
}

export default ControlesZoom
