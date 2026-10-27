import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { usePendingInvitations } from '../../hooks/usePendingInvitations'
import { colorAvatar, iniciales } from '../../utils/avatar'
import ConfirmModal from '../ConfirmModal/ConfirmModal'
import styles from './AppShell.module.css'

function claseNav({ isActive }) {
  return isActive ? `${styles.itemNav} ${styles.itemNavActivo}` : styles.itemNav
}

// Marco común de las páginas autenticadas: barra superior + menú lateral.
// El buscador solo aparece si la página pasa `onBusqueda`. Si la página ya
// maneja las invitaciones (Perfil), pasa `totalInvitaciones` para que el
// badge se actualice junto con ella.
function AppShell({ busqueda, onBusqueda, totalInvitaciones, children }) {
  const navigate = useNavigate()
  const { usuario } = useAuth()
  const { invitaciones } = usePendingInvitations()
  const [confirmarLogout, setConfirmarLogout] = useState(false)
  const pendientes = totalInvitaciones ?? invitaciones.length
  const colorUsuario = colorAvatar(usuario?.id)

  function handleConfirmarLogout() {
    localStorage.removeItem('access_token')
    navigate('/login', { replace: true })
  }

  return (
    <div className={styles.pagina}>
      <header className={styles.barraSuperior}>
        <Link to="/dashboard" className={styles.marca}>
          <span className={styles.logo}>
            <i className="ti ti-hierarchy-2" />
          </span>
          Gestor de Diagramas UML
        </Link>

        {onBusqueda && (
          <label className={styles.buscador}>
            <i className="ti ti-search" />
            <input
              type="search"
              placeholder="Buscar proyectos por nombre..."
              value={busqueda}
              onChange={(event) => onBusqueda(event.target.value)}
            />
          </label>
        )}

        <Link to="/perfil" className={styles.usuario}>
          <span className={styles.nombreUsuario}>{usuario?.nombre ?? '...'}</span>
          <span className={styles.avatarUsuario} style={{ background: colorUsuario.fondo, color: colorUsuario.texto }}>
            {iniciales(usuario?.nombre)}
          </span>
        </Link>
      </header>

      <div className={styles.cuerpo}>
        <aside className={styles.sidebar}>
          <span className={styles.seccionTitulo}>Espacio de trabajo</span>
          <nav className={styles.navegacion}>
            <NavLink to="/dashboard" className={claseNav}>
              <i className="ti ti-layout-grid" /> Proyectos
            </NavLink>
            <NavLink to="/perfil" className={claseNav}>
              <i className="ti ti-user" /> Mi perfil
              {pendientes > 0 && (
                <span className={styles.badgeNav} title="Invitaciones pendientes">
                  {pendientes}
                </span>
              )}
            </NavLink>
          </nav>
          <button type="button" className={styles.itemNav} onClick={() => setConfirmarLogout(true)}>
            <i className="ti ti-logout" /> Cerrar sesión
          </button>
        </aside>

        <main className={styles.contenido}>{children}</main>
      </div>

      {confirmarLogout && (
        <ConfirmModal
          icono="ti-logout"
          titulo="Cerrar sesión"
          mensaje="¿Seguro que querés cerrar sesión?"
          textoConfirmar="Cerrar sesión"
          onConfirm={handleConfirmarLogout}
          onCancel={() => setConfirmarLogout(false)}
        />
      )}
    </div>
  )
}

export default AppShell
