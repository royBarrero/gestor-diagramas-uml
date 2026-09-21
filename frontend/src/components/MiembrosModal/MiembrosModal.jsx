import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import ConfirmModal from '../ConfirmModal/ConfirmModal'
import { useSocketNotificaciones } from '../../hooks/useSocketNotificaciones'
import { api } from '../../services/api'
import styles from './MiembrosModal.module.css'

function MiembrosModal({ proyecto, onClose, onCambio }) {
  const [miembros, setMiembros] = useState([])
  const [cargando, setCargando] = useState(true)
  const [email, setEmail] = useState('')
  const [invitando, setInvitando] = useState(false)
  const [mensaje, setMensaje] = useState(null)
  const [miembroAQuitar, setMiembroAQuitar] = useState(null)

  function cargarMiembros() {
    api
      .get(`/proyectos/${proyecto.id}/miembros`)
      .then(({ data }) => setMiembros(data))
      .catch(() =>
        setMensaje({ tipo: 'error', texto: 'No se pudieron cargar los integrantes.' })
      )
      .finally(() => setCargando(false))
  }

  useEffect(() => {
    cargarMiembros()
  }, [])

  useSocketNotificaciones({
    miembro_agregado: (payload) => {
      if (payload?.proyecto_id === proyecto.id) cargarMiembros()
    },
  })

  async function handleInvitar(event) {
    event.preventDefault()
    setMensaje(null)
    setInvitando(true)
    try {
      await api.post(`/proyectos/${proyecto.id}/invitaciones`, { email })
      setMensaje({ tipo: 'exito', texto: 'Invitación enviada.' })
      setEmail('')
    } catch (err) {
      setMensaje({
        tipo: 'error',
        texto: err.response?.data?.detail ?? 'No se pudo enviar la invitación.',
      })
    } finally {
      setInvitando(false)
    }
  }

  async function handleConfirmarQuitar() {
    try {
      await api.delete(`/proyectos/${proyecto.id}/miembros/${miembroAQuitar.id}`)
      onCambio()
      onClose()
    } catch (err) {
      setMensaje({
        tipo: 'error',
        texto: err.response?.data?.detail ?? 'No se pudo quitar al integrante.',
      })
      setMiembroAQuitar(null)
    }
  }

  return createPortal(
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(event) => event.stopPropagation()}>
        <h2 className={styles.titulo}>Miembros de {proyecto.nombre}</h2>

        <form className={styles.form} onSubmit={handleInvitar}>
          <label className={styles.label} htmlFor="email-invitado">
            Invitar por email
          </label>
          <div className={styles.filaInvitar}>
            <input
              id="email-invitado"
              type="email"
              className={styles.input}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <button type="submit" className={styles.botonInvitar} disabled={invitando}>
              {invitando ? 'Invitando...' : 'Invitar'}
            </button>
          </div>
        </form>

        {mensaje && (
          <p className={mensaje.tipo === 'error' ? styles.error : styles.exito}>
            {mensaje.texto}
          </p>
        )}

        <ul className={styles.listaMiembros}>
          {cargando ? (
            <p className={styles.textoMuted}>Cargando integrantes...</p>
          ) : (
            miembros.map((miembro) => (
              <li key={miembro.id} className={styles.itemMiembro}>
                <div>
                  <span className={styles.nombreMiembro}>{miembro.nombre}</span>
                  <span className={styles.emailMiembro}>{miembro.email}</span>
                </div>
                <div className={styles.filaAcciones}>
                  <span className={styles.rolBadge}>
                    {miembro.rol === 'administrador' ? 'Administrador' : 'Colaborador'}
                  </span>
                  {!miembro.es_creador && (
                    <button
                      type="button"
                      className={styles.botonQuitar}
                      onClick={() => setMiembroAQuitar(miembro)}
                    >
                      Quitar
                    </button>
                  )}
                </div>
              </li>
            ))
          )}
        </ul>

        <button type="button" className={styles.botonCerrar} onClick={onClose}>
          Cerrar
        </button>
      </div>

      {miembroAQuitar && (
        <ConfirmModal
          titulo="Quitar integrante"
          mensaje={`¿Seguro que querés quitar a "${miembroAQuitar.nombre}" del proyecto?`}
          onConfirm={handleConfirmarQuitar}
          onCancel={() => setMiembroAQuitar(null)}
        />
      )}
    </div>,
    document.body
  )
}

export default MiembrosModal
