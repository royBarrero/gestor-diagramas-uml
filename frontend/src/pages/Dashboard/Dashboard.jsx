import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ConfirmModal from '../../components/ConfirmModal/ConfirmModal'
import MiembrosModal from '../../components/MiembrosModal/MiembrosModal'
import ProyectoFormModal from '../../components/ProyectoFormModal/ProyectoFormModal'
import { useAuth } from '../../contexts/AuthContext'
import { usePendingInvitations } from '../../hooks/usePendingInvitations'
import { api } from '../../services/api'
import styles from './Dashboard.module.css'

function Dashboard() {
  const { usuario } = useAuth()
  const { invitaciones } = usePendingInvitations()
  const [proyectos, setProyectos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [modalForm, setModalForm] = useState(null)
  const [proyectoAEliminar, setProyectoAEliminar] = useState(null)
  const [proyectoMiembros, setProyectoMiembros] = useState(null)

  function cargarProyectos() {
    api
      .get('/proyectos/mis-proyectos')
      .then(({ data }) => setProyectos(data))
      .catch(() => setError('No se pudieron cargar los proyectos.'))
      .finally(() => setCargando(false))
  }

  useEffect(() => {
    cargarProyectos()
  }, [])

  function handleGuardado() {
    setModalForm(null)
    cargarProyectos()
  }

  async function handleConfirmarEliminar() {
    try {
      await api.delete(`/proyectos/${proyectoAEliminar.id}`)
      setProyectoAEliminar(null)
      cargarProyectos()
    } catch (err) {
      setError(err.response?.data?.detail ?? 'No se pudo eliminar el proyecto.')
      setProyectoAEliminar(null)
    }
  }

  return (
    <div className={`${styles.pagina} grid-bg`}>
      <header className={styles.header}>
        <h1 className={styles.titulo}>Tus proyectos</h1>
        <div className={styles.headerAcciones}>
          <button
            type="button"
            className={styles.botonNuevo}
            onClick={() => setModalForm({ modo: 'crear' })}
          >
            + Nuevo proyecto
          </button>
          <Link to="/perfil" className={styles.avatarUsuario}>
            {usuario?.nombre ?? '...'}
            {invitaciones.length > 0 && (
              <span className={styles.puntoInvitacion} title="Tenés invitaciones pendientes" />
            )}
          </Link>
        </div>
      </header>

      {error && <p className={styles.error}>{error}</p>}

      {cargando ? (
        <p className={styles.textoMuted}>Cargando proyectos...</p>
      ) : proyectos.length === 0 ? (
        <p className={styles.textoMuted}>Todavía no tenés proyectos. Creá el primero.</p>
      ) : (
        <div className={styles.grilla}>
          {proyectos.map((proyecto) => (
            <Link key={proyecto.id} to={`/proyecto/${proyecto.id}/pizarra`} className={styles.tarjeta}>
              <span className={styles.rolBadge}>
                {proyecto.rol === 'administrador' ? 'Administrador' : 'Colaborador'}
              </span>
              <h2 className={styles.nombreProyecto}>{proyecto.nombre}</h2>
              <span className={styles.colaboradores}>
                {proyecto.total_miembros} integrante{proyecto.total_miembros === 1 ? '' : 's'}
              </span>

              {proyecto.rol === 'administrador' && (
                <div className={styles.accionesTarjeta}>
                  <button
                    type="button"
                    className={styles.botonEditar}
                    onClick={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setModalForm({ modo: 'editar', proyecto })
                    }}
                  >
                    Editar
                  </button>
                  <button
                    type="button"
                    className={styles.botonEditar}
                    onClick={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setProyectoMiembros(proyecto)
                    }}
                  >
                    Miembros
                  </button>
                  <button
                    type="button"
                    className={styles.botonEliminar}
                    onClick={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setProyectoAEliminar(proyecto)
                    }}
                  >
                    Eliminar
                  </button>
                </div>
              )}
            </Link>
          ))}
        </div>
      )}

      {modalForm && (
        <ProyectoFormModal
          modo={modalForm.modo}
          proyectoInicial={modalForm.proyecto ?? null}
          onGuardado={handleGuardado}
          onCancelar={() => setModalForm(null)}
        />
      )}

      {proyectoAEliminar && (
        <ConfirmModal
          titulo="Eliminar proyecto"
          mensaje={`¿Seguro que querés eliminar "${proyectoAEliminar.nombre}"? Esta acción no se puede deshacer.`}
          onConfirm={handleConfirmarEliminar}
          onCancel={() => setProyectoAEliminar(null)}
        />
      )}

      {proyectoMiembros && (
        <MiembrosModal
          proyecto={proyectoMiembros}
          onClose={() => setProyectoMiembros(null)}
          onCambio={cargarProyectos}
        />
      )}
    </div>
  )
}

export default Dashboard
