import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AppShell from '../../components/AppShell/AppShell'
import CuentaPerfil from '../../components/Perfil/CuentaPerfil'
import { useAuth } from '../../contexts/AuthContext'
import { usePendingInvitations } from '../../hooks/usePendingInvitations'
import { api } from '../../services/api'
import { colorAvatar, iniciales } from '../../utils/avatar'
import { fechaRelativa } from '../../utils/fechaRelativa'
import styles from './Perfil.module.css'

const MAX_ACTIVIDAD = 5
const MAX_EQUIPO = 6

function formatearFecha(fechaIso) {
  if (!fechaIso) return ''
  return new Date(fechaIso).toLocaleDateString('es-AR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function Avatar({ id, nombre, tamano = 'normal' }) {
  const color = colorAvatar(id)
  return (
    <span
      className={tamano === 'grande' ? styles.avatarGrande : styles.avatar}
      style={{ background: color.fondo, color: color.texto }}
      aria-hidden="true"
    >
      {iniciales(nombre)}
    </span>
  )
}

// Compañeros con los que el usuario comparte proyectos, ordenados por cantidad.
function calcularEquipo(proyectos, idUsuario) {
  const porId = new Map()
  for (const proyecto of proyectos) {
    for (const miembro of proyecto.miembros ?? []) {
      if (miembro.id === idUsuario) continue
      const actual = porId.get(miembro.id) ?? { ...miembro, enComun: 0 }
      actual.enComun += 1
      porId.set(miembro.id, actual)
    }
  }
  return [...porId.values()].sort((a, b) => b.enComun - a.enComun || a.nombre.localeCompare(b.nombre))
}

function ordenarPorActividad(proyectos) {
  return [...proyectos].sort((a, b) => {
    if (!a.updated_at) return 1
    if (!b.updated_at) return -1
    return new Date(b.updated_at) - new Date(a.updated_at)
  })
}

function Perfil() {
  const navigate = useNavigate()
  const { usuario, cargando: cargandoUsuario } = useAuth()
  const { invitaciones, cargando: cargandoInvitaciones, recargar: recargarInvitaciones } =
    usePendingInvitations()
  const [proyectos, setProyectos] = useState([])
  const [cargandoProyectos, setCargandoProyectos] = useState(true)
  const [errorInvitacion, setErrorInvitacion] = useState(null)
  const [procesando, setProcesando] = useState(null)
  const [copiado, setCopiado] = useState(false)
  const temporizadorCopiado = useRef(null)

  useEffect(() => {
    api
      .get('/proyectos/mis-proyectos')
      .then(({ data }) => setProyectos(data))
      .finally(() => setCargandoProyectos(false))
  }, [])

  useEffect(() => () => clearTimeout(temporizadorCopiado.current), [])

  async function handleCopiarEmail() {
    try {
      await navigator.clipboard.writeText(usuario.email)
      setCopiado(true)
      clearTimeout(temporizadorCopiado.current)
      temporizadorCopiado.current = setTimeout(() => setCopiado(false), 1800)
    } catch {
      // Sin permiso de portapapeles: no hacemos nada.
    }
  }

  async function handleAceptarInvitacion(invitacion) {
    setErrorInvitacion(null)
    setProcesando({ id: invitacion.id, accion: 'aceptar' })
    try {
      await api.post(`/invitaciones/${invitacion.id}/aceptar`)
      navigate('/dashboard')
    } catch (err) {
      setErrorInvitacion(err.response?.data?.detail ?? 'No se pudo aceptar la invitación.')
      setProcesando(null)
    }
  }

  async function handleRechazarInvitacion(invitacion) {
    setErrorInvitacion(null)
    setProcesando({ id: invitacion.id, accion: 'rechazar' })
    try {
      await api.post(`/invitaciones/${invitacion.id}/rechazar`)
      recargarInvitaciones()
    } catch (err) {
      setErrorInvitacion(err.response?.data?.detail ?? 'No se pudo rechazar la invitación.')
    } finally {
      setProcesando(null)
    }
  }

  const totalAdmin = proyectos.filter((p) => p.rol === 'administrador').length
  const totalColab = proyectos.length - totalAdmin
  const equipo = calcularEquipo(proyectos, usuario?.id)
  const actividad = ordenarPorActividad(proyectos).slice(0, MAX_ACTIVIDAD)
  const estadisticas = [
    { icono: 'ti-folders', valor: proyectos.length, etiqueta: 'Proyectos' },
    {
      icono: 'ti-box-model-2',
      valor: proyectos.reduce((total, p) => total + (p.total_clases ?? 0), 0),
      etiqueta: 'Clases diseñadas',
    },
    {
      icono: 'ti-git-merge',
      valor: proyectos.reduce((total, p) => total + (p.total_relaciones ?? 0), 0),
      etiqueta: 'Relaciones',
    },
    { icono: 'ti-users-group', valor: equipo.length, etiqueta: 'Compañeros de equipo' },
  ]

  return (
    <AppShell totalInvitaciones={cargandoInvitaciones ? undefined : invitaciones.length}>
      <div className={styles.perfil}>
        {/* ---------- Portada ---------- */}
        <section className={styles.portada}>
          <div className={styles.banner} />
          <div className={styles.portadaCuerpo}>
            {cargandoUsuario || !usuario ? (
              <div className={styles.portadaCargando}>
                <span className={`${styles.esqueleto} ${styles.esqueletoAvatar}`} />
                <span className={`${styles.esqueleto} ${styles.esqueletoLinea}`} />
              </div>
            ) : (
              <>
                <Avatar id={usuario.id} nombre={usuario.nombre} tamano="grande" />
                <div className={styles.identidad}>
                  <h1 className={styles.nombre}>{usuario.nombre}</h1>
                  <div className={styles.datosFila}>
                    <button type="button" className={styles.email} onClick={handleCopiarEmail} title="Copiar correo">
                      <i className="ti ti-mail" aria-hidden="true" />
                      {usuario.email}
                      <i className={`ti ${copiado ? 'ti-check' : 'ti-copy'}`} aria-hidden="true" />
                      <span className={styles.copiado} aria-live="polite">
                        {copiado ? '¡Copiado!' : ''}
                      </span>
                    </button>
                    <span className={styles.miembroDesde}>
                      <i className="ti ti-calendar" aria-hidden="true" />
                      Miembro desde {formatearFecha(usuario.created_at)} ·{' '}
                      {fechaRelativa(usuario.created_at).toLowerCase()}
                    </span>
                  </div>
                  {!cargandoProyectos && (
                    <div className={styles.chips}>
                      <span className={styles.chipAdmin}>
                        Administrador en {totalAdmin} proyecto{totalAdmin === 1 ? '' : 's'}
                      </span>
                      <span className={styles.chipColab}>
                        Colaborador en {totalColab} proyecto{totalColab === 1 ? '' : 's'}
                      </span>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </section>

        {/* ---------- Estadísticas ---------- */}
        <section className={styles.estadisticas} aria-label="Estadísticas">
          {estadisticas.map((estadistica) => (
            <div key={estadistica.etiqueta} className={styles.estadistica}>
              <span className={styles.iconoEstadistica}>
                <i className={`ti ${estadistica.icono}`} aria-hidden="true" />
              </span>
              <div>
                {cargandoProyectos ? (
                  <span className={`${styles.esqueleto} ${styles.esqueletoNumero}`} />
                ) : (
                  <span className={styles.valorEstadistica}>{estadistica.valor}</span>
                )}
                <span className={styles.etiquetaEstadistica}>{estadistica.etiqueta}</span>
              </div>
            </div>
          ))}
        </section>

        <div className={styles.columnas}>
          <div className={styles.columnaPrincipal}>
            {/* ---------- Invitaciones ---------- */}
            <section className={styles.tarjeta}>
              <header className={styles.tarjetaCabecera}>
                <h2 className={styles.tarjetaTitulo}>
                  <i className="ti ti-mail-opened" aria-hidden="true" /> Invitaciones pendientes
                </h2>
                {invitaciones.length > 0 && <span className={styles.contador}>{invitaciones.length}</span>}
              </header>

              {errorInvitacion && (
                <p className={styles.avisoError} role="alert">
                  <i className="ti ti-alert-circle" aria-hidden="true" />
                  {errorInvitacion}
                </p>
              )}

              {cargandoInvitaciones ? (
                <span className={`${styles.esqueleto} ${styles.esqueletoFila}`} />
              ) : invitaciones.length === 0 ? (
                <div className={styles.vacio}>
                  <span className={styles.iconoVacio}>
                    <i className="ti ti-inbox" aria-hidden="true" />
                  </span>
                  <p>No tenés invitaciones pendientes.</p>
                  <span>Cuando alguien te invite a un proyecto, la vas a ver acá.</span>
                </div>
              ) : (
                <ul className={styles.listaInvitaciones}>
                  {invitaciones.map((invitacion) => {
                    const esta = procesando?.id === invitacion.id
                    return (
                      <li key={invitacion.id} className={styles.invitacion}>
                        <Avatar id={invitacion.invitado_por_id} nombre={invitacion.invitado_por} />
                        <div className={styles.invitacionTexto}>
                          <p>
                            <strong>{invitacion.invitado_por}</strong> te invitó a{' '}
                            <strong className={styles.resaltado}>{invitacion.proyecto_nombre}</strong>
                          </p>
                          {invitacion.created_at && (
                            <span className={styles.textoTenue}>{fechaRelativa(invitacion.created_at)}</span>
                          )}
                        </div>
                        <div className={styles.invitacionAcciones}>
                          <button
                            type="button"
                            className={styles.botonSecundario}
                            disabled={procesando !== null}
                            onClick={() => handleRechazarInvitacion(invitacion)}
                          >
                            {esta && procesando.accion === 'rechazar' ? 'Rechazando...' : 'Rechazar'}
                          </button>
                          <button
                            type="button"
                            className={styles.botonPrimario}
                            disabled={procesando !== null}
                            onClick={() => handleAceptarInvitacion(invitacion)}
                          >
                            {esta && procesando.accion === 'aceptar' ? 'Aceptando...' : 'Aceptar'}
                          </button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>

            {/* ---------- Actividad reciente ---------- */}
            <section className={styles.tarjeta}>
              <header className={styles.tarjetaCabecera}>
                <h2 className={styles.tarjetaTitulo}>
                  <i className="ti ti-activity" aria-hidden="true" /> Actividad reciente
                </h2>
                <Link to="/dashboard" className={styles.linkSecundario}>
                  Ver todos los proyectos
                </Link>
              </header>

              {cargandoProyectos ? (
                <>
                  <span className={`${styles.esqueleto} ${styles.esqueletoFila}`} />
                  <span className={`${styles.esqueleto} ${styles.esqueletoFila}`} />
                </>
              ) : actividad.length === 0 ? (
                <div className={styles.vacio}>
                  <span className={styles.iconoVacio}>
                    <i className="ti ti-folder-plus" aria-hidden="true" />
                  </span>
                  <p>Todavía no participás de ningún proyecto.</p>
                  <Link to="/dashboard" className={styles.linkSecundario}>
                    Crear mi primer proyecto
                  </Link>
                </div>
              ) : (
                <ol className={styles.lineaTiempo}>
                  {actividad.map((proyecto) => {
                    const esAdmin = proyecto.rol === 'administrador'
                    return (
                      <li key={proyecto.id} className={styles.evento}>
                        <span className={styles.puntoEvento} aria-hidden="true" />
                        <div className={styles.eventoCuerpo}>
                          <div className={styles.eventoTitulo}>
                            <span className={styles.eventoNombre}>{proyecto.nombre}</span>
                            <span className={esAdmin ? styles.rolAdmin : styles.rolColab}>
                              {esAdmin ? 'Administrador' : 'Colaborador'}
                            </span>
                          </div>
                          <span className={styles.textoTenue}>
                            {proyecto.total_clases} clase{proyecto.total_clases === 1 ? '' : 's'} ·{' '}
                            {proyecto.total_relaciones} relaci{proyecto.total_relaciones === 1 ? 'ón' : 'ones'} ·{' '}
                            {fechaRelativa(proyecto.updated_at)}
                          </span>
                        </div>
                        <Link to={`/proyecto/${proyecto.id}/pizarra`} className={styles.linkAbrir}>
                          Abrir <i className="ti ti-arrow-right" aria-hidden="true" />
                        </Link>
                      </li>
                    )
                  })}
                </ol>
              )}
            </section>

            {/* ---------- Cuenta ---------- */}
            <section className={styles.tarjeta}>
              <header className={styles.tarjetaCabecera}>
                <h2 className={styles.tarjetaTitulo}>
                  <i className="ti ti-settings" aria-hidden="true" /> Cuenta
                </h2>
              </header>
              {usuario ? (
                <CuentaPerfil />
              ) : (
                <span className={`${styles.esqueleto} ${styles.esqueletoFila}`} />
              )}
            </section>
          </div>

          {/* ---------- Tu equipo ---------- */}
          <aside className={styles.columnaLateral}>
            <section className={styles.tarjeta}>
              <header className={styles.tarjetaCabecera}>
                <h2 className={styles.tarjetaTitulo}>
                  <i className="ti ti-users" aria-hidden="true" /> Tu equipo
                </h2>
              </header>

              {cargandoProyectos ? (
                <span className={`${styles.esqueleto} ${styles.esqueletoFila}`} />
              ) : equipo.length === 0 ? (
                <div className={styles.vacio}>
                  <span className={styles.iconoVacio}>
                    <i className="ti ti-user-plus" aria-hidden="true" />
                  </span>
                  <p>Todavía no compartís proyectos.</p>
                  <span>Invitá a alguien desde la opción Miembros de un proyecto.</span>
                </div>
              ) : (
                <ul className={styles.listaEquipo}>
                  {equipo.slice(0, MAX_EQUIPO).map((companero) => (
                    <li key={companero.id} className={styles.companero}>
                      <Avatar id={companero.id} nombre={companero.nombre} />
                      <div className={styles.companeroTexto}>
                        <span className={styles.companeroNombre}>{companero.nombre}</span>
                        <span className={styles.textoTenue}>
                          {companero.enComun} proyecto{companero.enComun === 1 ? '' : 's'} en común
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {equipo.length > MAX_EQUIPO && (
                <span className={styles.textoTenue}>y {equipo.length - MAX_EQUIPO} más</span>
              )}
            </section>
          </aside>
        </div>
      </div>
    </AppShell>
  )
}

export default Perfil
