import { useState } from 'react'
import { createPortal } from 'react-dom'
import { TIPOS_RELACION } from '../../constants/tiposRelacion'
import styles from './MultiplicidadModal.module.css'

// Edita una relación ya existente (tipo, multiplicidad, nombre) — se dispara
// desde el mini-menú de RelacionEdge.jsx cuando el edge está seleccionado.
function EditarRelacionModal({ relacion, onConfirmar, onCancelar }) {
  const datos = relacion.data ?? {}
  const [tipo, setTipo] = useState(datos.tipo ?? 'asociacion')
  const [origen, setOrigen] = useState(datos.multiplicidadOrigen ?? '')
  const [destino, setDestino] = useState(datos.multiplicidadDestino ?? '')
  const [nombre, setNombre] = useState(datos.nombre ?? '')

  function handleSubmit(event) {
    event.preventDefault()
    onConfirmar({
      tipo,
      multiplicidadOrigen: origen.trim() || null,
      multiplicidadDestino: destino.trim() || null,
      nombre: nombre.trim() || undefined,
    })
  }

  return createPortal(
    <div className={styles.overlay} onClick={onCancelar}>
      <div className={styles.modal} onClick={(event) => event.stopPropagation()}>
        <h2 className={styles.titulo}>Editar relación</h2>
        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.label} htmlFor="rel-tipo">
            Tipo de relación
          </label>
          <select
            id="rel-tipo"
            className={styles.input}
            value={tipo}
            onChange={(event) => setTipo(event.target.value)}
          >
            {TIPOS_RELACION.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.etiqueta}
              </option>
            ))}
          </select>

          <label className={styles.label} htmlFor="edit-mult-origen">
            Extremo origen (ej: 1, 0..1, 0..*, 1..*)
          </label>
          <input
            id="edit-mult-origen"
            className={styles.input}
            value={origen}
            onChange={(event) => setOrigen(event.target.value)}
            autoFocus
          />

          <label className={styles.label} htmlFor="edit-mult-destino">
            Extremo destino
          </label>
          <input
            id="edit-mult-destino"
            className={styles.input}
            value={destino}
            onChange={(event) => setDestino(event.target.value)}
          />

          <label className={styles.label} htmlFor="edit-rel-nombre">
            Nombre de la relación (opcional)
          </label>
          <input
            id="edit-rel-nombre"
            className={styles.input}
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
          />

          <div className={styles.acciones}>
            <button type="button" className={styles.botonCancelar} onClick={onCancelar}>
              Cancelar
            </button>
            <button type="submit" className={styles.botonGuardar}>
              Guardar
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}

export default EditarRelacionModal
