import { useRef } from 'react'
import { createPortal } from 'react-dom'
import styles from './MultiplicidadModal.module.css'

// CU10: elegir un archivo (JSON por ahora) o, como atajo, disparar la
// digitalización por foto ya existente (CU09) para "importar" desde una imagen.
function ImportarModal({ onArchivoSeleccionado, onSeleccionarImagen, onCancelar }) {
  const inputJsonRef = useRef(null)
  const inputXmiRef = useRef(null)

  function handleArchivo(event, formato) {
    const archivo = event.target.files?.[0]
    event.target.value = ''
    if (archivo) onArchivoSeleccionado(archivo, formato)
  }

  return createPortal(
    <div className={styles.overlay} onClick={onCancelar}>
      <div className={styles.modal} onClick={(event) => event.stopPropagation()}>
        <h2 className={styles.titulo}>Importar diagrama</h2>
        <p className={styles.label}>Esto va a reemplazar el diagrama actual.</p>

        <input
          type="file"
          accept=".json,application/json"
          ref={inputJsonRef}
          style={{ display: 'none' }}
          onChange={(event) => handleArchivo(event, 'json')}
        />
        <input
          type="file"
          accept=".xmi,.xml,application/xml,text/xml"
          ref={inputXmiRef}
          style={{ display: 'none' }}
          onChange={(event) => handleArchivo(event, 'xmi')}
        />

        <div className={styles.acciones} style={{ justifyContent: 'flex-start' }}>
          <button type="button" className={styles.botonGuardar} onClick={() => inputJsonRef.current?.click()}>
            JSON
          </button>
          <button type="button" className={styles.botonGuardar} onClick={() => inputXmiRef.current?.click()}>
            XMI
          </button>
          <button type="button" className={styles.botonGuardar} onClick={onSeleccionarImagen}>
            Imagen (foto)
          </button>
        </div>
        <div className={styles.acciones}>
          <button type="button" className={styles.botonCancelar} onClick={onCancelar}>
            Cancelar
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

export default ImportarModal
