import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import ConfirmModal from '../ConfirmModal/ConfirmModal'
import CampoTexto from '../CampoTexto/CampoTexto'
import { useAuth } from '../../contexts/AuthContext'
import { useSocketNotificaciones } from '../../hooks/useSocketNotificaciones'
import { api } from '../../services/api'
import { colorAvatar, iniciales } from '../../utils/avatar'
import styles from './MiembrosModal.module.css'

function MiembrosModal({ proyecto, onClose, onCambio }) {
  const { usuario } = useAuth()
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

  // Escape cierra este modal, salvo que esté abierta la confirmación de "quitar".
  useEffect(() => {
    function handleTecla(event) {
      if (event.key === 'Escape' && !miembroAQuitar) onClose()
    }
    document.addEventListener('keydown', handleTecla)
    return () => document.removeEventListener('keydown', handleTecla)
  }, [miembroAQuitar, onClose])

  async function handleInvitar(event) {
    event.preventDefault()
    setMensaje(null)
    setInvitando(true)
    try {
      await api.post(`/proyectos/${proyecto.id}/invitaciones`, { email })
      setMensaje({ tipo: 'exito', texto: `Invitación enviada a ${email}.` })
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
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="miembros-titulo"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.cabecera}>
          <span className={styles.icono} aria-hidden="true">
            <i className="ti ti-users-plus" />
          </span>
          <div className={styles.cabeceraTexto}>
            <h2 id="miembros-titulo" className={styles.titulo}>
              Miembros del proyecto
            </h2>
            <p className={styles.subtitulo}>{proyecto.nombre}</p>
          </div>
          <button type="button" className={styles.cerrar} onClick={onClose} aria-label="Cerrar">
            <i className="ti ti-x" />
          </button>
        </header>

        <form className={styles.invitar} onSubmit={handleInvitar}>
          <div className={styles.filaInvitar}>
            <CampoTexto
              id="email-invitado"
              label="Invitar colaborador"
              icono="ti-mail"
              type="email"
              placeholder="correo@ejemplo.com"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value)
                setMensaje(null)
              }}
              autoFocus
              required
            />
            <button type="submit" className={styles.botonInvitar} disabled={invitando}>
              {invitando ? (
                'Enviando...'
              ) : (
                <>
                  <i className="ti ti-send" aria-hidden="true" /> Invitar
                </>
              )}
            </button>
          </div>
          <p className={styles.ayuda}>
            <i className="ti ti-info-circle" aria-hidden="true" />
            Se suma como colaborador cuando acepta la invitación desde su perfil.
          </p>
        </form>

        {mensaje && (
          <p className={mensaje.tipo === 'error' ? styles.error : styles.exito} role={mensaje.tipo === 'error' ? 'alert' : 'status'}>
            <i
              className={`ti ${mensaje.tipo === 'error' ? 'ti-alert-circle' : 'ti-circle-check'}`}
              aria-hidden="true"
            />
            {mensaje.texto}
          </p>
        )}

        <section className={styles.integrantes}>
          <h3 className={styles.integrantesTitulo}>
            Integrantes
            {!cargando && <span className={styles.contador}>{miembros.length}</span>}
          </h3>

          {cargando ? (
            <div className={styles.listaMiembros}>
              <span className={styles.esqueleto} />
              <span className={styles.esqueleto} />
            </div>
          ) : (
            <ul className={styles.listaMiembros}>
              {miembros.map((miembro) => {
                const color = colorAvatar(miembro.id)
                const esAdmin = miembro.rol === 'administrador'
                return (
                  <li key={miembro.id} className={styles.itemMiembro}>
                    <span
                      className={styles.avatar}
                      style={{ background: color.fondo, color: color.texto }}
                      aria-hidden="true"
                    >
                      {iniciales(miembro.nombre)}
                    </span>
                    <div className={styles.datosMiembro}>
                      <span className={styles.nombreMiembro}>
                        {miembro.nombre}
                        {miembro.id === usuario?.id && <span className={styles.vos}>Vos</span>}
                        {miembro.es_creador && (
                          <i className={`ti ti-crown ${styles.corona}`} title="Creador del proyecto" />
                        )}
                      </span>
                      <span className={styles.emailMiembro}>{miembro.email}</span>
                    </div>
                    <span className={esAdmin ? styles.rolAdmin : styles.rolColab}>
                      {esAdmin ? 'Administrador' : 'Colaborador'}
                    </span>
                    {!miembro.es_creador && (
                      <button
                        type="button"
                        className={styles.botonQuitar}
                        onClick={() => setMiembroAQuitar(miembro)}
                        aria-label={`Quitar a ${miembro.nombre}`}
                        title="Quitar del proyecto"
                      >
                        <i className="ti ti-user-minus" />
                      </button>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </div>

      {miembroAQuitar && (
        <ConfirmModal
          variante="peligro"
          icono="ti-user-minus"
          titulo="Quitar integrante"
          mensaje={`¿Seguro que querés quitar a "${miembroAQuitar.nombre}" del proyecto? Va a perder el acceso al diagrama.`}
          textoConfirmar="Quitar"
          textoProcesando="Quitando..."
          onConfirm={handleConfirmarQuitar}
          onCancel={() => setMiembroAQuitar(null)}
        />
      )}
    </div>,
    document.body
  )
}

export default MiembrosModal
