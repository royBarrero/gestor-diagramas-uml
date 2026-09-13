import { createPortal } from 'react-dom'
import styles from './ConfirmModal.module.css'

function ConfirmModal({ titulo, mensaje, onConfirm, onCancel }) {
  return createPortal(
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {titulo && <h2 className={styles.titulo}>{titulo}</h2>}
        <p className={styles.mensaje}>{mensaje}</p>
        <div className={styles.acciones}>
          <button type="button" className={styles.botonCancelar} onClick={onCancel}>
            Cancelar
          </button>
          <button type="button" className={styles.botonConfirmar} onClick={onConfirm}>
            Confirmar
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

export default ConfirmModal
