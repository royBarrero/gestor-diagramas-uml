import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import AppShell from '../../components/AppShell/AppShell'
import ConfirmModal from '../../components/ConfirmModal/ConfirmModal'
import ProyectoCard from '../../components/Dashboard/ProyectoCard'
import MiembrosModal from '../../components/MiembrosModal/MiembrosModal'
import ProyectoFormModal from '../../components/ProyectoFormModal/ProyectoFormModal'
import { useSocketNotificaciones } from '../../hooks/useSocketNotificaciones'
import { api } from '../../services/api'
import styles from './Dashboard.module.css'

const FILTROS = [
  { valor: 'todos', etiqueta: 'Todos' },
  { valor: 'administrador', etiqueta: 'Soy administrador' },
  { valor: 'colaborador', etiqueta: 'Soy colaborador' },
]

function Dashboard() {
  const [proyectos, setProyectos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [busqueda, setBusqueda] = useState('')
  const [filtroRol, setFiltroRol] = useState('todos')
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

  useSocketNotificaciones({ miembro_agregado: cargarProyectos })

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

  const textoBusqueda = busqueda.trim().toLowerCase()
  const proyectosVisibles = proyectos.filter(
    (proyecto) =>
      (filtroRol === 'todos' || proyecto.rol === filtroRol) &&
      proyecto.nombre.toLowerCase().includes(textoBusqueda),
  )
  // Crear un proyecto te deja como administrador: no tiene sentido ofrecerlo
  // en la vista "Soy colaborador", ni cuando se está buscando.
  const mostrarCrear = filtroRol !== 'colaborador' && !textoBusqueda

  return (
    <AppShell busqueda={busqueda} onBusqueda={setBusqueda}>
      <section className={styles.encabezado}>
        <div>
          <div className={styles.filaTitulo}>
            <h1 className={styles.titulo}>Tus proyectos</h1>
            <span className={styles.contador}>
              {proyectos.length} proyecto{proyectos.length === 1 ? '' : 's'}
            </span>
          </div>
          <p className={styles.subtitulo}>
            Diseñá diagramas de clases UML en equipo, en tiempo real, y generá el backend y el frontend a partir
            de ellos.
          </p>
        </div>
        <button type="button" className={styles.botonNuevo} onClick={() => setModalForm({ modo: 'crear' })}>
          <i className="ti ti-plus" /> Nuevo proyecto
        </button>
      </section>

      <div className={styles.filtros}>
        {FILTROS.map((filtro) => (
          <button
            key={filtro.valor}
            type="button"
            className={`${styles.filtro} ${filtroRol === filtro.valor ? styles.filtroActivo : ''}`}
            onClick={() => setFiltroRol(filtro.valor)}
          >
            {filtro.etiqueta}
            {filtro.valor === 'todos' && ` (${proyectos.length})`}
          </button>
        ))}
      </div>

      {error && <p className={styles.error}>{error}</p>}

      {cargando ? (
        <p className={styles.textoMuted}>Cargando proyectos...</p>
      ) : (
        <>
          {proyectosVisibles.length === 0 &&
            (textoBusqueda ? (
              <div className={styles.vacio}>
                <span className={styles.iconoVacio}>
                  <i className="ti ti-search" aria-hidden="true" />
                </span>
                <p className={styles.tituloVacio}>Ningún proyecto coincide con “{busqueda.trim()}”</p>
                <span>Probá con otro nombre o cambiá el filtro.</span>
              </div>
            ) : filtroRol === 'colaborador' ? (
              <div className={styles.vacio}>
                <span className={styles.iconoVacio}>
                  <i className="ti ti-users" aria-hidden="true" />
                </span>
                <p className={styles.tituloVacio}>Todavía no sos colaborador en ningún proyecto</p>
                <span>
                  Cuando alguien te invite, vas a ver la invitación en <Link to="/perfil">Mi perfil</Link>.
                </span>
              </div>
            ) : (
              <p className={styles.textoMuted}>
                {filtroRol === 'administrador'
                  ? 'Todavía no administrás ningún proyecto. Creá uno.'
                  : 'Todavía no tenés proyectos. Creá el primero.'}
              </p>
            ))}

          {(proyectosVisibles.length > 0 || mostrarCrear) && (
            <div className={styles.grilla}>
              {proyectosVisibles.map((proyecto) => (
                <ProyectoCard
                  key={proyecto.id}
                  proyecto={proyecto}
                  onEditar={(p) => setModalForm({ modo: 'editar', proyecto: p })}
                  onMiembros={setProyectoMiembros}
                  onEliminar={setProyectoAEliminar}
                />
              ))}
              {mostrarCrear && (
                <button type="button" className={styles.tarjetaCrear} onClick={() => setModalForm({ modo: 'crear' })}>
                  <span className={styles.iconoCrear}>
                    <i className="ti ti-plus" />
                  </span>
                  <span className={styles.tituloCrear}>Crear proyecto</span>
                  <span className={styles.textoCrear}>Empezá con un lienzo vacío e invitá a tu equipo.</span>
                </button>
              )}
            </div>
          )}
        </>
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
          variante="peligro"
          icono="ti-trash"
          titulo="Eliminar proyecto"
          mensaje={`Vas a eliminar "${proyectoAEliminar.nombre}". Esta acción no se puede deshacer.`}
          detalles={[
            {
              icono: 'ti-box-model-2',
              texto: `Se borra el diagrama: ${proyectoAEliminar.total_clases} clase${proyectoAEliminar.total_clases === 1 ? '' : 's'} y ${proyectoAEliminar.total_relaciones} relaci${proyectoAEliminar.total_relaciones === 1 ? 'ón' : 'ones'}`,
            },
            {
              icono: 'ti-users',
              texto: `${proyectoAEliminar.total_miembros} integrante${proyectoAEliminar.total_miembros === 1 ? '' : 's'} pierde${proyectoAEliminar.total_miembros === 1 ? '' : 'n'} el acceso`,
            },
          ]}
          textoConfirmar="Eliminar proyecto"
          textoProcesando="Eliminando..."
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
    </AppShell>
  )
}

export default Dashboard
