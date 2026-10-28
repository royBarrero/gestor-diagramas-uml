import { useState } from 'react'
import { TIPOS_RELACION } from '../../constants/tiposRelacion'
import ModalPizarra from './ModalPizarra'
import styles from './ModalPizarra.module.css'

const MULTIPLICIDADES = ['1', '0..1', '0..*', '1..*']

// También lo usa EditarRelacionModal.
export function CampoMultiplicidad({ id, etiqueta, valor, onCambiar, autoFocus }) {
  return (
    <div className={styles.campo}>
      <label className={styles.label} htmlFor={id}>
        {etiqueta}
      </label>
      <input
        id={id}
        className={`${styles.input} ${styles.inputMono}`}
        value={valor}
        onChange={(event) => onCambiar(event.target.value)}
        autoFocus={autoFocus}
      />
      <div className={styles.chips}>
        {MULTIPLICIDADES.map((opcion) => (
          <button
            key={opcion}
            type="button"
            className={`${styles.chip} ${valor.trim() === opcion ? styles.chipActivo : ''}`}
            onClick={() => onCambiar(opcion)}
          >
            {opcion}
          </button>
        ))}
      </div>
    </div>
  )
}

// `origen`/`destino` son los nombres de las clases que se están relacionando.
function MultiplicidadModal({ tipo, origen, destino, onConfirmar, onCancelar }) {
  const [multOrigen, setMultOrigen] = useState('1')
  const [multDestino, setMultDestino] = useState('1')
  const [nombre, setNombre] = useState('')
  const etiquetaTipo = TIPOS_RELACION.find((t) => t.valor === tipo)?.etiqueta ?? 'Relación'

  function handleSubmit(event) {
    event.preventDefault()
    onConfirmar(multOrigen.trim() || '1', multDestino.trim() || '1', nombre.trim())
  }

  return (
    <ModalPizarra
      titulo={`Nueva ${etiquetaTipo.toLowerCase()}`}
      subtitulo={origen && destino ? `${origen} → ${destino}` : undefined}
      icono="ti-arrows-left-right"
      onCerrar={onCancelar}
    >
      <form className={styles.form} onSubmit={handleSubmit}>
        <CampoMultiplicidad
          id="mult-origen"
          etiqueta={`Multiplicidad en ${origen ?? 'el origen'}`}
          valor={multOrigen}
          onCambiar={setMultOrigen}
          autoFocus
        />
        <CampoMultiplicidad
          id="mult-destino"
          etiqueta={`Multiplicidad en ${destino ?? 'el destino'}`}
          valor={multDestino}
          onCambiar={setMultDestino}
        />

        <div className={styles.campo}>
          <label className={styles.label} htmlFor="rel-nombre">
            Nombre de la relación <span className={styles.opcional}>(opcional, ej: realiza, compra)</span>
          </label>
          <input
            id="rel-nombre"
            className={styles.input}
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
          />
        </div>

        <div className={styles.acciones}>
          <button type="button" className={styles.botonCancelar} onClick={onCancelar}>
            Cancelar
          </button>
          <button type="submit" className={styles.botonPrimario}>
            Crear relación
          </button>
        </div>
      </form>
    </ModalPizarra>
  )
}

export default MultiplicidadModal
