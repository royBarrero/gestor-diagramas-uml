import { usePizarra } from '../../contexts/PizarraContext'
import { TIPOS_RELACION } from '../../constants/tiposRelacion'
import styles from './Toolbar.module.css'

// Barra flotante sobre el lienzo: deshacer/rehacer y herramientas de relación.
function Toolbar() {
  const { tipoRelacionActivo, seleccionarTipoRelacion, origenConexionId, deshacer, rehacer, puedeDeshacer, puedeRehacer } =
    usePizarra()

  return (
    <div className={styles.barra}>
      <button type="button" title="Deshacer (Ctrl+Z)" className={styles.botonIcono} onClick={deshacer} disabled={!puedeDeshacer}>
        <i className="ti ti-arrow-back-up" />
      </button>
      <button type="button" title="Rehacer (Ctrl+Y)" className={styles.botonIcono} onClick={rehacer} disabled={!puedeRehacer}>
        <i className="ti ti-arrow-forward-up" />
      </button>
      <span className={styles.separador} />

      {TIPOS_RELACION.map((tipo) => (
        <button
          key={tipo.valor}
          type="button"
          title={tipo.etiqueta}
          className={`${styles.boton} ${tipoRelacionActivo === tipo.valor ? styles.activo : ''}`}
          onClick={() => seleccionarTipoRelacion(tipo.valor)}
        >
          <i className={`ti ${tipo.icono}`} />
          <span>{tipo.etiqueta}</span>
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
