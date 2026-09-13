import { useParams } from 'react-router-dom'
import styles from './Pizarra.module.css'

function Pizarra() {
  const { id } = useParams()

  return (
    <div className={styles.pagina}>
      <header className={styles.header}>
        <h1 className={styles.titulo}>Diagrama de Clases — Proyecto #{id}</h1>
        <span className={styles.colaboradores}>🟢 3 colaboradores en línea</span>
      </header>

      {/* Acá va a ir el canvas de React Flow (@xyflow/react) — todavía no implementado. */}
      <div className={`${styles.canvas} grid-bg`} />
    </div>
  )
}

export default Pizarra
