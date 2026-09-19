import { createPortal } from 'react-dom'
import styles from './MultiplicidadModal.module.css'

// CU10: elegir el formato para exportar el diagrama actual.
function ExportarModal({ onSeleccionarJson, onSeleccionarPng, onSeleccionarXmi, onCancelar }) {
  return createPortal(
    <div className={styles.overlay} onClick={onCancelar}>
      <div className={styles.modal} onClick={(event) => event.stopPropagation()}>
        <h2 className={styles.titulo}>Exportar diagrama</h2>
        <div className={styles.acciones} style={{ justifyContent: 'flex-start' }}>
          <button type="button" className={styles.botonGuardar} onClick={onSeleccionarJson}>
            JSON
          </button>
          <button type="button" className={styles.botonGuardar} onClick={onSeleccionarPng}>
            Imagen (PNG)
          </button>
          <button type="button" className={styles.botonGuardar} onClick={onSeleccionarXmi}>
            XMI
          </button>
        </div>
        <div className={styles.acciones}>
          <button type="button" className={styles.botonCancelar} onClick={onCancelar}>
            Cerrar
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

export default ExportarModal
