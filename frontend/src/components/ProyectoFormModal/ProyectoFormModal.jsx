import { useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../../services/api'
import styles from './ProyectoFormModal.module.css'

function ProyectoFormModal({ modo, proyectoInicial, onGuardado, onCancelar }) {
  const [nombre, setNombre] = useState(proyectoInicial?.nombre ?? '')
  const [descripcion, setDescripcion] = useState(proyectoInicial?.descripcion ?? '')
  const [error, setError] = useState(null)
  const [guardando, setGuardando] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setGuardando(true)

    try {
      if (modo === 'crear') {
        await api.post('/proyectos', { nombre, descripcion: descripcion || null })
      } else {
        await api.put(`/proyectos/${proyectoInicial.id}`, {
          nombre,
          descripcion: descripcion || null,
        })
      }
      onGuardado()
    } catch (err) {
      setError(err.response?.data?.detail ?? 'No se pudo guardar el proyecto.')
    } finally {
      setGuardando(false)
    }
  }

  return createPortal(
    <div className={styles.overlay} onClick={onCancelar}>
      <div className={styles.modal} onClick={(event) => event.stopPropagation()}>
        <h2 className={styles.titulo}>{modo === 'crear' ? 'Nuevo proyecto' : 'Editar proyecto'}</h2>
        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.label} htmlFor="nombre">
            Nombre
          </label>
          <input
            id="nombre"
            className={styles.input}
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
            required
            maxLength={150}
          />

          <label className={styles.label} htmlFor="descripcion">
            Descripción
          </label>
          <textarea
            id="descripcion"
            className={styles.textarea}
            value={descripcion}
            onChange={(event) => setDescripcion(event.target.value)}
            rows={4}
          />

          {error && <p className={styles.error}>{error}</p>}

          <div className={styles.acciones}>
            <button
              type="button"
              className={styles.botonCancelar}
              onClick={onCancelar}
              disabled={guardando}
            >
              Cancelar
            </button>
            <button type="submit" className={styles.botonGuardar} disabled={guardando}>
              {guardando ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}

export default ProyectoFormModal
