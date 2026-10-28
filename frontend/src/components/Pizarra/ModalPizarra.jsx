import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import styles from './ModalPizarra.module.css'

// Marco común de los modales de la pizarra (multiplicidad, editar relación,
// exportar, importar): overlay, encabezado con ícono, botón cerrar y Esc.
// El contenido usa las clases exportadas por ModalPizarra.module.css.
function ModalPizarra({ titulo, subtitulo, icono, onCerrar, children }) {
  useEffect(() => {
    function handleTecla(event) {
      if (event.key === 'Escape') onCerrar()
    }
    document.addEventListener('keydown', handleTecla)
    return () => document.removeEventListener('keydown', handleTecla)
  }, [onCerrar])

  return createPortal(
    <div className={styles.overlay} onClick={onCerrar}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-pizarra-titulo"
        onClick={(event) => event.stopPropagation()}
      >
        <div className={styles.header}>
          <span className={styles.icono} aria-hidden="true">
            <i className={`ti ${icono}`} />
          </span>
          <div className={styles.headerTexto}>
            <h2 id="modal-pizarra-titulo" className={styles.titulo}>
              {titulo}
            </h2>
            {subtitulo && <p className={styles.subtitulo}>{subtitulo}</p>}
          </div>
          <button type="button" className={styles.botonCerrar} onClick={onCerrar} title="Cerrar">
            <i className="ti ti-x" />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body
  )
}

// Tarjeta clickeable con ícono, título y descripción (exportar / importar).
export function OpcionModal({ icono, titulo, descripcion, onClick }) {
  return (
    <button type="button" className={styles.opcion} onClick={onClick}>
      <span className={styles.opcionIcono} aria-hidden="true">
        <i className={`ti ${icono}`} />
      </span>
      <span className={styles.opcionTexto}>
        <span className={styles.opcionTitulo}>{titulo}</span>
        <span className={styles.opcionDescripcion}>{descripcion}</span>
      </span>
      <i className={`ti ti-chevron-right ${styles.opcionFlecha}`} aria-hidden="true" />
    </button>
  )
}

export default ModalPizarra
