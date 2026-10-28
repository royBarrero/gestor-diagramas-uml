import { useRef } from 'react'
import ModalPizarra, { OpcionModal } from './ModalPizarra'
import styles from './ModalPizarra.module.css'

// CU10: elegir un archivo JSON/XMI o, como atajo, disparar la digitalización
// por foto ya existente (CU09) para "importar" desde una imagen.
function ImportarModal({ onArchivoSeleccionado, onSeleccionarImagen, onCancelar }) {
  const inputJsonRef = useRef(null)
  const inputXmiRef = useRef(null)

  function handleArchivo(event, formato) {
    const archivo = event.target.files?.[0]
    event.target.value = ''
    if (archivo) onArchivoSeleccionado(archivo, formato)
  }

  return (
    <ModalPizarra
      titulo="Importar diagrama"
      subtitulo="Elegí de dónde traer el diagrama."
      icono="ti-upload"
      onCerrar={onCancelar}
    >
      <div className={styles.aviso}>
        <i className="ti ti-alert-triangle" aria-hidden="true" />
        Esto va a reemplazar el diagrama actual.
      </div>

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

      <div className={styles.opciones}>
        <OpcionModal
          icono="ti-braces"
          titulo="JSON"
          descripcion="Un diagrama exportado desde esta app."
          onClick={() => inputJsonRef.current?.click()}
        />
        <OpcionModal
          icono="ti-file-code"
          titulo="XMI"
          descripcion="Exportado desde Enterprise Architect."
          onClick={() => inputXmiRef.current?.click()}
        />
        <OpcionModal
          icono="ti-camera"
          titulo="Imagen (foto)"
          descripcion="Una foto o captura de un diagrama de clases."
          onClick={onSeleccionarImagen}
        />
      </div>
    </ModalPizarra>
  )
}

export default ImportarModal
