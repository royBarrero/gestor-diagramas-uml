import ModalPizarra, { OpcionModal } from './ModalPizarra'
import styles from './ModalPizarra.module.css'

// CU10: elegir el formato para exportar el diagrama actual.
function ExportarModal({ onSeleccionarJson, onSeleccionarPng, onSeleccionarXmi, onCancelar }) {
  return (
    <ModalPizarra
      titulo="Exportar diagrama"
      subtitulo="Elegí el formato del archivo que se va a descargar."
      icono="ti-download"
      onCerrar={onCancelar}
    >
      <div className={styles.opciones}>
        <OpcionModal
          icono="ti-braces"
          titulo="JSON"
          descripcion="Para volver a importarlo en esta app."
          onClick={onSeleccionarJson}
        />
        <OpcionModal icono="ti-photo" titulo="Imagen (PNG)" descripcion="Una captura del lienzo." onClick={onSeleccionarPng} />
        <OpcionModal
          icono="ti-file-code"
          titulo="XMI"
          descripcion="Compatible con Enterprise Architect."
          onClick={onSeleccionarXmi}
        />
      </div>
    </ModalPizarra>
  )
}

export default ExportarModal
