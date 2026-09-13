import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import ConfirmModal from '../../components/ConfirmModal/ConfirmModal'
import { useAuth } from '../../contexts/AuthContext'
import { usePendingInvitations } from '../../hooks/usePendingInvitations'
import { api } from '../../services/api'
import styles from './Perfil.module.css'

function formatearFecha(fechaIso) {
  if (!fechaIso) return ''
  return new Date(fechaIso).toLocaleDateString('es-AR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function Perfil() {
  const navigate = useNavigate()
  const { usuario, cargando: cargandoUsuario } = useAuth()
  const { invitaciones, cargando: cargandoInvitaciones, recargar: recargarInvitaciones } =
    usePendingInvitations()
  const [proyectos, setProyectos] = useState([])
  const [cargandoProyectos, setCargandoProyectos] = useState(true)
  const [mostrarModal, setMostrarModal] = useState(false)
  const [errorInvitacion, setErrorInvitacion] = useState(null)

  function cargarProyectos() {
    api
      .get('/proyectos/mis-proyectos')
      .then(({ data }) => setProyectos(data))
      .finally(() => setCargandoProyectos(false))
  }

  useEffect(() => {
    cargarProyectos()
  }, [])

  function handleConfirmarLogout() {
    localStorage.removeItem('access_token')
    navigate('/login', { replace: true })
  }

  async function handleAceptarInvitacion(invitacion) {
    setErrorInvitacion(null)
    try {
      await api.post(`/invitaciones/${invitacion.id}/aceptar`)
      navigate('/dashboard')
    } catch (err) {
      setErrorInvitacion(err.response?.data?.detail ?? 'No se pudo aceptar la invitación.')
    }
  }

  async function handleRechazarInvitacion(invitacion) {
    setErrorInvitacion(null)
    try {
      await api.post(`/invitaciones/${invitacion.id}/rechazar`)
      recargarInvitaciones()
    } catch (err) {
      setErrorInvitacion(err.response?.data?.detail ?? 'No se pudo rechazar la invitación.')
    }
  }

  return (
    <div className={`${styles.pagina} grid-bg`}>
      <div className={styles.contenedor}>
        <Link to="/dashboard" className={styles.volver}>
          ← Volver a mis proyectos
        </Link>

        <section className={styles.tarjetaDatos}>
          <h1 className={styles.titulo}>Mi perfil</h1>
          {cargandoUsuario ? (
            <p className={styles.textoMuted}>Cargando datos...</p>
          ) : (
            <dl className={styles.datos}>
              <dt>Nombre</dt>
              <dd>{usuario?.nombre}</dd>
              <dt>Email</dt>
              <dd>{usuario?.email}</dd>
              <dt>Usuario desde</dt>
              <dd>{formatearFecha(usuario?.created_at)}</dd>
            </dl>
          )}
        </section>

        {!cargandoInvitaciones && invitaciones.length > 0 && (
          <section className={styles.tarjetaProyectos}>
            <h2 className={styles.subtitulo}>Invitaciones pendientes</h2>
            {errorInvitacion && <p className={styles.textoMuted}>{errorInvitacion}</p>}
            <ul className={styles.listaProyectos}>
              {invitaciones.map((invitacion) => (
                <li key={invitacion.id} className={styles.itemProyecto}>
                  <span className={styles.nombreProyecto}>
                    {invitacion.proyecto_nombre}
                    <span className={styles.textoMuted}> — invitado por {invitacion.invitado_por}</span>
                  </span>
                  <div className={styles.filaAccionesInvitacion}>
                    <button
                      type="button"
                      className={styles.botonAceptar}
                      onClick={() => handleAceptarInvitacion(invitacion)}
                    >
                      Aceptar
                    </button>
                    <button
                      type="button"
                      className={styles.botonRechazar}
                      onClick={() => handleRechazarInvitacion(invitacion)}
                    >
                      Rechazar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className={styles.tarjetaProyectos}>
          <h2 className={styles.subtitulo}>Mis proyectos</h2>
          {cargandoProyectos ? (
            <p className={styles.textoMuted}>Cargando proyectos...</p>
          ) : proyectos.length === 0 ? (
            <p className={styles.textoMuted}>Todavía no participás de ningún proyecto.</p>
          ) : (
            <ul className={styles.listaProyectos}>
              {proyectos.map((proyecto) => (
                <li key={proyecto.id} className={styles.itemProyecto}>
                  <span className={styles.nombreProyecto}>{proyecto.nombre}</span>
                  <span className={styles.rolBadge}>{proyecto.rol}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <button
          type="button"
          className={styles.botonLogout}
          onClick={() => setMostrarModal(true)}
        >
          Cerrar sesión
        </button>
      </div>

      {mostrarModal && (
        <ConfirmModal
          titulo="Cerrar sesión"
          mensaje="¿Seguro que querés cerrar sesión?"
          onConfirm={handleConfirmarLogout}
          onCancel={() => setMostrarModal(false)}
        />
      )}
    </div>
  )
}

export default Perfil
