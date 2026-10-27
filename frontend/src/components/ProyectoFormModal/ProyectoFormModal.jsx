import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../../services/api'
import CampoTexto from '../CampoTexto/CampoTexto'
import styles from './ProyectoFormModal.module.css'

const MAX_NOMBRE = 150

function ProyectoFormModal({ modo, proyectoInicial, onGuardado, onCancelar }) {
  const [nombre, setNombre] = useState(proyectoInicial?.nombre ?? '')
  const [descripcion, setDescripcion] = useState(proyectoInicial?.descripcion ?? '')
  const [error, setError] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const esCrear = modo === 'crear'

  useEffect(() => {
    function handleTecla(event) {
      if (event.key === 'Escape' && !guardando) onCancelar()
    }
    document.addEventListener('keydown', handleTecla)
    return () => document.removeEventListener('keydown', handleTecla)
  }, [guardando, onCancelar])

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setGuardando(true)

    try {
      if (esCrear) {
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

  let textoBoton = esCrear ? 'Crear proyecto' : 'Guardar cambios'
  if (guardando) textoBoton = esCrear ? 'Creando...' : 'Guardando...'

  return createPortal(
    <div className={styles.overlay} onClick={() => !guardando && onCancelar()}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="proyecto-form-titulo"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.cabecera}>
          <span className={styles.icono} aria-hidden="true">
            <i className={`ti ${esCrear ? 'ti-folder-plus' : 'ti-pencil'}`} />
          </span>
          <div className={styles.cabeceraTexto}>
            <h2 id="proyecto-form-titulo" className={styles.titulo}>
              {esCrear ? 'Nuevo proyecto' : 'Editar proyecto'}
            </h2>
            <p className={styles.subtitulo}>
              {esCrear
                ? 'Dale un nombre y contá de qué se trata. Después podés invitar a tu equipo.'
                : 'Actualizá el nombre o la descripción del proyecto.'}
            </p>
          </div>
          <button
            type="button"
            className={styles.cerrar}
            onClick={onCancelar}
            disabled={guardando}
            aria-label="Cerrar"
          >
            <i className="ti ti-x" />
          </button>
        </header>

        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.campoNombre}>
            <CampoTexto
              id="proyecto-nombre"
              label="Nombre"
              icono="ti-folder"
              placeholder="Ej.: Sistema de Biblioteca"
              value={nombre}
              onChange={(event) => setNombre(event.target.value)}
              maxLength={MAX_NOMBRE}
              autoFocus
              required
            />
            <span className={styles.contadorCaracteres}>
              {nombre.length}/{MAX_NOMBRE}
            </span>
          </div>

          <div className={styles.campo}>
            <label className={styles.label} htmlFor="proyecto-descripcion">
              Descripción <span className={styles.opcional}>(opcional)</span>
            </label>
            <textarea
              id="proyecto-descripcion"
              className={styles.textarea}
              placeholder="¿Qué vas a modelar?"
              value={descripcion}
              onChange={(event) => setDescripcion(event.target.value)}
              rows={4}
            />
          </div>

          {error && (
            <p className={styles.error} role="alert">
              <i className="ti ti-alert-circle" aria-hidden="true" />
              {error}
            </p>
          )}

          <div className={styles.acciones}>
            <button type="button" className={styles.botonCancelar} onClick={onCancelar} disabled={guardando}>
              Cancelar
            </button>
            <button type="submit" className={styles.botonGuardar} disabled={guardando}>
              {textoBoton}
              {esCrear && !guardando && <i className="ti ti-arrow-right" aria-hidden="true" />}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}

export default ProyectoFormModal
