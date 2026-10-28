import { usePizarra } from '../../contexts/PizarraContext'
import styles from './RielClases.module.css'

function RielClases() {
  const { agregarClase, listaClasesAbierta, alternarListaClases, cerrarListaClases } = usePizarra()

  function handleNuevaClase() {
    cerrarListaClases()
    agregarClase()
  }

  return (
    <nav className={styles.riel} aria-label="Herramientas de clases">
      <button
        type="button"
        className={`${styles.boton} ${listaClasesAbierta ? styles.activo : ''}`}
        onClick={alternarListaClases}
        title="Lista de clases"
      >
        <i className="ti ti-list" />
      </button>
      <button type="button" className={`${styles.boton} ${styles.primario}`} onClick={handleNuevaClase} title="Nueva clase">
        <i className="ti ti-plus" />
      </button>
    </nav>
  )
}

export default RielClases
