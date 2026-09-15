import { useState } from 'react'
import { createPortal } from 'react-dom'
import styles from './MultiplicidadModal.module.css'

function MultiplicidadModal({ onConfirmar, onCancelar }) {
  const [origen, setOrigen] = useState('1')
  const [destino, setDestino] = useState('1')
  const [nombre, setNombre] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    onConfirmar(origen.trim() || '1', destino.trim() || '1', nombre.trim())
  }

  return createPortal(
    <div className={styles.overlay} onClick={onCancelar}>
      <div className={styles.modal} onClick={(event) => event.stopPropagation()}>
        <h2 className={styles.titulo}>Multiplicidad de la relación</h2>
        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.label} htmlFor="mult-origen">
            Extremo origen (ej: 1, 0..1, 0..*, 1..*)
          </label>
          <input
            id="mult-origen"
            className={styles.input}
            value={origen}
            onChange={(event) => setOrigen(event.target.value)}
            autoFocus
          />

          <label className={styles.label} htmlFor="mult-destino">
            Extremo destino
          </label>
          <input
            id="mult-destino"
            className={styles.input}
            value={destino}
            onChange={(event) => setDestino(event.target.value)}
          />

          <label className={styles.label} htmlFor="rel-nombre">
            Nombre de la relación (opcional, ej: realiza, compra, genera)
          </label>
          <input
            id="rel-nombre"
            className={styles.input}
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
          />

          <div className={styles.acciones}>
            <button type="button" className={styles.botonCancelar} onClick={onCancelar}>
              Cancelar
            </button>
            <button type="submit" className={styles.botonGuardar}>
              Crear relación
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}

export default MultiplicidadModal
