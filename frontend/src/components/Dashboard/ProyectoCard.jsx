import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { colorAvatar, iniciales } from '../../utils/avatar'
import { fechaRelativa } from '../../utils/fechaRelativa'
import GenerarCodigoMenu from './GenerarCodigoMenu'
import styles from './ProyectoCard.module.css'

const MAX_AVATARES = 4

function ProyectoCard({ proyecto, onEditar, onMiembros, onEliminar }) {
  const esAdmin = proyecto.rol === 'administrador'
  const [menuAbierto, setMenuAbierto] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuAbierto) return undefined
    function handleClickAfuera(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuAbierto(false)
      }
    }
    document.addEventListener('mousedown', handleClickAfuera)
    return () => document.removeEventListener('mousedown', handleClickAfuera)
  }, [menuAbierto])

  function elegir(accion) {
    setMenuAbierto(false)
    accion(proyecto)
  }

  const miembros = proyecto.miembros ?? []
  const avatares = miembros.slice(0, MAX_AVATARES)
  const restantes = miembros.length - avatares.length

  return (
    <article className={styles.tarjeta}>
      <div className={styles.cabecera}>
        <span className={esAdmin ? styles.rolAdmin : styles.rolColab}>
          {esAdmin ? 'Administrador' : 'Colaborador'}
        </span>

        {esAdmin && (
          <div className={styles.menuContenedor} ref={menuRef}>
            <button
              type="button"
              className={styles.botonMenu}
              aria-label="Opciones del proyecto"
              onClick={() => setMenuAbierto((a) => !a)}
            >
              <i className="ti ti-dots-vertical" />
            </button>
            {menuAbierto && (
              <div className={styles.menu}>
                <button type="button" className={styles.itemMenu} onClick={() => elegir(onEditar)}>
                  <i className="ti ti-pencil" /> Editar
                </button>
                <button type="button" className={styles.itemMenu} onClick={() => elegir(onMiembros)}>
                  <i className="ti ti-users" /> Miembros
                </button>
                <button
                  type="button"
                  className={`${styles.itemMenu} ${styles.itemPeligro}`}
                  onClick={() => elegir(onEliminar)}
                >
                  <i className="ti ti-trash" /> Eliminar
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <h2 className={styles.nombre}>{proyecto.nombre}</h2>
      {proyecto.descripcion ? (
        <p className={styles.descripcion}>{proyecto.descripcion}</p>
      ) : (
        <p className={`${styles.descripcion} ${styles.sinDescripcion}`}>Sin descripción</p>
      )}

      <div className={styles.resumen}>
        <span>
          {proyecto.total_clases} clase{proyecto.total_clases === 1 ? '' : 's'} ·{' '}
          {proyecto.total_relaciones} relaci{proyecto.total_relaciones === 1 ? 'ón' : 'ones'}
        </span>
        <div className={styles.avatares}>
          {avatares.map((miembro) => {
            const color = colorAvatar(miembro.id)
            return (
              <span
                key={miembro.id}
                className={styles.avatar}
                style={{ background: color.fondo, color: color.texto }}
                title={miembro.nombre}
              >
                {iniciales(miembro.nombre)}
              </span>
            )
          })}
          {restantes > 0 && <span className={`${styles.avatar} ${styles.avatarMas}`}>+{restantes}</span>}
        </div>
      </div>

      <footer className={styles.pie}>
        <span className={styles.fecha}>{fechaRelativa(proyecto.updated_at)}</span>
        <div className={styles.botones}>
          {esAdmin && (
            <div className={styles.boton}>
              <GenerarCodigoMenu proyectoId={proyecto.id} backendGeneradoEn={proyecto.backend_generado_en} />
            </div>
          )}
          <Link to={`/proyecto/${proyecto.id}/pizarra`} className={`${styles.boton} ${styles.botonAbrir}`}>
            Abrir <i className="ti ti-arrow-right" />
          </Link>
        </div>
      </footer>
    </article>
  )
}

export default ProyectoCard
