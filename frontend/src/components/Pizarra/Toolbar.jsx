import { usePizarra } from '../../contexts/PizarraContext'
import styles from './Toolbar.module.css'

const TIPOS = [
  { valor: 'asociacion', etiqueta: 'Asociación', icono: 'ti-arrow-narrow-right' },
  { valor: 'herencia', etiqueta: 'Herencia', icono: 'ti-triangle' },
  { valor: 'agregacion', etiqueta: 'Agregación', icono: 'ti-diamond' },
  { valor: 'composicion', etiqueta: 'Composición', icono: 'ti-square-rotated' },
  { valor: 'dependencia', etiqueta: 'Dependencia', icono: 'ti-arrow-guide' },
]

function Toolbar() {
  const { tipoRelacionActivo, seleccionarTipoRelacion, origenConexionId } = usePizarra()

  return (
    <div className={styles.barra}>
      {TIPOS.map((tipo) => (
        <button
          key={tipo.valor}
          type="button"
          title={tipo.etiqueta}
          className={`${styles.boton} ${tipoRelacionActivo === tipo.valor ? styles.activo : ''}`}
          onClick={() => seleccionarTipoRelacion(tipo.valor)}
        >
          <i className={`ti ${tipo.icono}`} />
          <span className={styles.etiqueta}>{tipo.etiqueta}</span>
        </button>
      ))}

      {tipoRelacionActivo && (
        <span className={styles.ayuda}>
          {origenConexionId ? 'Ahora hacé click en la clase de destino' : 'Hacé click en la clase de origen'}
        </span>
      )}
    </div>
  )
}

export default Toolbar
