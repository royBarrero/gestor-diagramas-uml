import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Background, BackgroundVariant, ReactFlow, ReactFlowProvider } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api } from '../../services/api'
import { PizarraProvider, usePizarra } from '../../contexts/PizarraContext'
import { useAuth } from '../../contexts/AuthContext'
import { useDebouncedEffect } from '../../hooks/useDebouncedEffect'
import { useColaboracion } from '../../hooks/useColaboracion'
import { useComandoVoz } from '../../hooks/useComandoVoz'
import { useDigitalizacionImagen } from '../../hooks/useDigitalizacionImagen'
import { useExportarDiagrama } from '../../hooks/useExportarDiagrama'
import { useExportarImagen } from '../../hooks/useExportarImagen'
import { useImportarDiagrama } from '../../hooks/useImportarDiagrama'
import ClaseNode from '../../components/Pizarra/ClaseNode'
import RelacionEdge from '../../components/Pizarra/RelacionEdge'
import Toolbar from '../../components/Pizarra/Toolbar'
import RielClases from '../../components/Pizarra/RielClases'
import ListaClases from '../../components/Pizarra/ListaClases'
import InspectorClase from '../../components/Pizarra/InspectorClase'
import ControlesZoom from '../../components/Pizarra/ControlesZoom'
import AvisosEstado from '../../components/Pizarra/AvisosEstado'
import MultiplicidadModal from '../../components/Pizarra/MultiplicidadModal'
import EditarRelacionModal from '../../components/Pizarra/EditarRelacionModal'
import ExportarModal from '../../components/Pizarra/ExportarModal'
import ImportarModal from '../../components/Pizarra/ImportarModal'
import ArchivoMenu from '../../components/Pizarra/ArchivoMenu'
import ConfirmModal from '../../components/ConfirmModal/ConfirmModal'
import ErrorBoundaryLienzo from '../../components/Pizarra/ErrorBoundaryLienzo'
import styles from './Pizarra.module.css'

const tiposDeNodo = { clase: ClaseNode }
const tiposDeEdge = { relacion: RelacionEdge }

const PALETA_COLABORADORES = ['#4c8dff', '#e0a030', '#33b679', '#e05c5c', '#a06ce0', '#3fbfbf']
const colorPorUsuario = (id) => PALETA_COLABORADORES[id % PALETA_COLABORADORES.length]

// Traduce el estado de voz, foto, importación y exportación a los avisos que
// se muestran abajo al centro del lienzo ({ id, tipo, texto, detalle }).
function armarAvisos({
  estadoVoz,
  mensajeVoz,
  transcripcionVoz,
  estadoFoto,
  mensajeFoto,
  estadoImportar,
  mensajeImportar,
  estadoExportar,
  estadoExportarImagen,
}) {
  const avisos = []
  const escuche = transcripcionVoz ? ` · Escuché: "${transcripcionVoz}"` : ''

  if (estadoVoz === 'procesando') avisos.push({ id: 'voz', tipo: 'progreso', texto: 'Procesando comando…' })
  if (estadoVoz === 'aplicado') avisos.push({ id: 'voz', tipo: 'ok', texto: `${mensajeVoz} ✓${escuche}`, detalle: transcripcionVoz })
  if (estadoVoz === 'no_entendido')
    avisos.push({ id: 'voz', tipo: 'error', texto: `No entendí el comando: ${mensajeVoz}${escuche}`, detalle: transcripcionVoz })
  if (estadoVoz === 'error_ia') avisos.push({ id: 'voz', tipo: 'error', texto: 'El asistente de voz no está disponible ahora.' })
  if (estadoVoz === 'error') avisos.push({ id: 'voz', tipo: 'error', texto: mensajeVoz })

  if (estadoFoto === 'procesando') avisos.push({ id: 'foto', tipo: 'progreso', texto: 'Analizando imagen…' })
  if (estadoFoto === 'aplicado') avisos.push({ id: 'foto', tipo: 'ok', texto: 'Diagrama digitalizado ✓' })
  if (estadoFoto === 'parcial') avisos.push({ id: 'foto', tipo: 'ok', texto: `Digitalización parcial: ${mensajeFoto}` })
  if (estadoFoto === 'fallido') avisos.push({ id: 'foto', tipo: 'error', texto: `No se pudo digitalizar: ${mensajeFoto}` })
  if (estadoFoto === 'error_ia') avisos.push({ id: 'foto', tipo: 'error', texto: 'El servicio de visión no está disponible ahora.' })
  if (estadoFoto === 'error') avisos.push({ id: 'foto', tipo: 'error', texto: mensajeFoto })

  if (estadoImportar === 'procesando') avisos.push({ id: 'importar', tipo: 'progreso', texto: 'Importando…' })
  if (estadoImportar === 'aplicado') avisos.push({ id: 'importar', tipo: 'ok', texto: 'Diagrama importado ✓' })
  if (estadoImportar === 'formato_invalido')
    avisos.push({ id: 'importar', tipo: 'error', texto: `Archivo inválido: ${mensajeImportar}` })
  if (estadoImportar === 'error') avisos.push({ id: 'importar', tipo: 'error', texto: mensajeImportar })

  if (estadoExportar === 'error') avisos.push({ id: 'exportar', tipo: 'error', texto: 'No se pudo exportar el diagrama.' })
  if (estadoExportarImagen === 'error') avisos.push({ id: 'exportar-png', tipo: 'error', texto: 'No se pudo exportar la imagen.' })

  return avisos
}

function LienzoPizarra({ diagramaId, diagramaNombre, proyectoNombre }) {
  const {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    iniciarConexion,
    pendienteConexion,
    cancelarConexion,
    crearRelacion,
    claseAEliminarId,
    confirmarEliminarClase,
    cancelarEliminarClase,
    seleccionarClase,
    manejarClickParaConectar,
    cancelarOrigenConexion,
    reemplazarDiagrama,
    aplicarDiagramaLocal,
    deshacer,
    rehacer,
    iniciarArrastre,
    finalizarArrastre,
    seleccionId,
    claseSeleccionada,
    relacionAEditar,
    cancelarEdicionRelacion,
    editarRelacion,
    listaClasesAbierta,
    cerrarListaClases,
    tipoRelacionActivo,
  } = usePizarra()
  const { usuario } = useAuth()

  const [estadoGuardado, setEstadoGuardado] = useState('guardado')

  const { colaboradores, estadoConexion } = useColaboracion(diagramaId, {
    nodes,
    edges,
    reemplazarDiagrama,
    seleccionId,
  })
  const {
    estado: estadoVoz,
    mensaje: mensajeVoz,
    transcripcion: transcripcionVoz,
    alternarGrabacion,
  } = useComandoVoz(diagramaId, {
    onAplicado: aplicarDiagramaLocal,
  })
  const { estado: estadoFoto, mensaje: mensajeFoto, subirImagen } = useDigitalizacionImagen(diagramaId, {
    onAplicado: aplicarDiagramaLocal,
  })
  const inputFotoRef = useRef(null)

  function handleArchivoFoto(event) {
    const archivo = event.target.files?.[0]
    event.target.value = ''
    subirImagen(archivo)
  }

  const [modalAbierto, setModalAbierto] = useState(null) // null | 'exportar' | 'importar'
  const [importacionPendiente, setImportacionPendiente] = useState(null) // {archivo, formato} | null

  const canvasRef = useRef(null)
  const { estado: estadoExportar, exportar } = useExportarDiagrama(diagramaId)
  const { estado: estadoExportarImagen, exportarImagen } = useExportarImagen(canvasRef, diagramaNombre)
  const { estado: estadoImportar, mensaje: mensajeImportar, importar } = useImportarDiagrama(diagramaId, {
    onAplicado: aplicarDiagramaLocal,
  })

  // Ctrl+Z / Ctrl+Y (o Ctrl+Shift+Z) y Esc para cerrar el inspector y la lista
  // de clases. Dentro de un campo de texto se dejan las teclas al navegador.
  useEffect(() => {
    function manejarTecla(event) {
      const destino = event.target
      if (destino.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(destino.tagName)) return
      if (event.key === 'Escape') {
        seleccionarClase(null)
        cerrarListaClases()
        return
      }
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return
      const tecla = event.key.toLowerCase()
      if (tecla === 'z' && !event.shiftKey) {
        event.preventDefault()
        deshacer()
      } else if (tecla === 'y' || (tecla === 'z' && event.shiftKey)) {
        event.preventDefault()
        rehacer()
      }
    }
    window.addEventListener('keydown', manejarTecla)
    return () => window.removeEventListener('keydown', manejarTecla)
  }, [deshacer, rehacer, seleccionarClase, cerrarListaClases])

  const otrosColaboradores = colaboradores.filter((c) => c.id !== usuario?.id)

  const presenciaPorClase = {}
  otrosColaboradores.forEach((c) => {
    if (c.claseId) presenciaPorClase[c.claseId] = { nombre: c.nombre, color: colorPorUsuario(c.id) }
  })
  const nodesConPresencia = nodes.map((n) =>
    presenciaPorClase[n.id] ? { ...n, data: { ...n.data, presencia: presenciaPorClase[n.id] } } : n
  )

  useDebouncedEffect(
    () => {
      setEstadoGuardado('guardando')
      api
        .put(`/diagramas/${diagramaId}`, { contenido: { nodes, edges } })
        .then(() => setEstadoGuardado('guardado'))
        .catch(() => setEstadoGuardado('error'))
    },
    [nodes, edges],
    1500
  )

  function handleConfirmarMultiplicidad(multOrigen, multDestino, nombre) {
    crearRelacion(
      pendienteConexion.source,
      pendienteConexion.target,
      pendienteConexion.tipo,
      multOrigen,
      multDestino,
      nombre
    )
    cancelarConexion()
  }

  const nodoAEliminar = claseAEliminarId ? nodes.find((n) => n.id === claseAEliminarId) : null

  // Con una herramienta de relación activa, el click solo conecta: no abre el
  // inspector, que taparía las clases que se están relacionando.
  function handleClickNodo(event, node) {
    if (!tipoRelacionActivo) seleccionarClase(node.id)
    manejarClickParaConectar(node.id)
  }

  const avisos = armarAvisos({
    estadoVoz,
    mensajeVoz,
    transcripcionVoz,
    estadoFoto,
    mensajeFoto,
    estadoImportar,
    mensajeImportar,
    estadoExportar,
    estadoExportarImagen,
  })

  function handleClickLienzo() {
    cancelarOrigenConexion()
    seleccionarClase(null)
    cerrarListaClases()
  }

  return (
    <div className={styles.pagina}>
      <header className={styles.header}>
        <div className={styles.headerIzquierda}>
          <Link to="/dashboard" className={styles.botonIcono} title="Volver a mis proyectos">
            <i className="ti ti-arrow-left" />
          </Link>
          <h1 className={styles.titulo}>
            {proyectoNombre && (
              <>
                <span className={styles.tituloProyecto}>{proyectoNombre}</span>
                <span className={styles.tituloSeparador}>/</span>
              </>
            )}
            Diagrama de clases
          </h1>
          <span className={`${styles.estado} ${estadoGuardado === 'error' ? styles.estadoError : ''}`}>
            {estadoGuardado === 'guardando' && (
              <>
                <i className="ti ti-loader-2" /> Guardando…
              </>
            )}
            {estadoGuardado === 'guardado' && (
              <>
                <i className={`ti ti-check ${styles.iconoGuardado}`} /> Guardado
              </>
            )}
            {estadoGuardado === 'error' && (
              <>
                <i className="ti ti-alert-circle" /> Error al guardar
              </>
            )}
          </span>
        </div>

        <div className={styles.headerDerecha}>
          {estadoConexion !== 'conectado' && (
            <span className={styles.estadoConexion}>
              {estadoConexion === 'reconectando' ? 'Reconectando…' : 'Sin conexión'}
            </span>
          )}

          {otrosColaboradores.length > 0 && (
            <div className={styles.colaboradores} title={otrosColaboradores.map((c) => c.nombre).join(', ')}>
              {otrosColaboradores.map((c) => (
                <span key={c.id} className={styles.colaboradorAvatar} style={{ background: colorPorUsuario(c.id) }}>
                  {c.nombre?.[0]?.toUpperCase() ?? '?'}
                </span>
              ))}
            </div>
          )}

          <span className={styles.separadorHeader} />

          <button
            type="button"
            className={`${styles.botonIcono} ${estadoVoz === 'grabando' ? styles.botonGrabando : ''}`}
            onClick={alternarGrabacion}
            disabled={estadoVoz === 'procesando'}
            title={estadoVoz === 'grabando' ? 'Detener grabación' : 'Comando de voz'}
          >
            <i className={`ti ${estadoVoz === 'grabando' ? 'ti-player-stop' : 'ti-microphone'}`} />
          </button>

          <input
            type="file"
            accept="image/*"
            capture="environment"
            ref={inputFotoRef}
            onChange={handleArchivoFoto}
            style={{ display: 'none' }}
          />
          <button
            type="button"
            className={styles.botonIcono}
            onClick={() => inputFotoRef.current?.click()}
            disabled={estadoFoto === 'procesando'}
            title="Digitalizar diagrama por foto"
          >
            <i className="ti ti-camera" />
          </button>

          <ArchivoMenu onExportar={() => setModalAbierto('exportar')} onImportar={() => setModalAbierto('importar')} />
        </div>
      </header>

      <div className={styles.cuerpo}>
        <RielClases />

        <div className={styles.centro}>
          {/* Todo lo que flota sobre el lienzo queda fuera de canvasRef, así no
              sale en la exportación a PNG. */}
          <div className={styles.zonaLienzo}>
            <div className={styles.canvas} ref={canvasRef}>
              <ErrorBoundaryLienzo>
                <ReactFlow
                  nodes={nodesConPresencia}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={iniciarConexion}
                  onNodeDragStart={iniciarArrastre}
                  onNodeDragStop={finalizarArrastre}
                  onNodeClick={handleClickNodo}
                  onPaneClick={handleClickLienzo}
                  nodeTypes={tiposDeNodo}
                  edgeTypes={tiposDeEdge}
                  connectionMode="loose"
                  connectionRadius={40}
                  fitView
                >
                  {/* Cuadrícula de dos niveles: líneas finas cada 24px y guías cada 120px. */}
                  <Background
                    id="fina"
                    variant={BackgroundVariant.Lines}
                    gap={24}
                    lineWidth={1}
                    color="rgba(255,255,255,0.035)"
                  />
                  <Background
                    id="guia"
                    variant={BackgroundVariant.Lines}
                    gap={120}
                    lineWidth={1}
                    color="rgba(255,255,255,0.07)"
                  />
                </ReactFlow>
              </ErrorBoundaryLienzo>
            </div>
            <Toolbar />
            <ControlesZoom />
            <AvisosEstado avisos={avisos} />
            {listaClasesAbierta && <ListaClases nodos={nodesConPresencia} />}
            {claseSeleccionada && !tipoRelacionActivo && <InspectorClase key={claseSeleccionada.id} />}
          </div>
        </div>
      </div>

      {pendienteConexion && (
        <MultiplicidadModal
          tipo={pendienteConexion.tipo}
          origen={nodes.find((n) => n.id === pendienteConexion.source)?.data.nombre}
          destino={nodes.find((n) => n.id === pendienteConexion.target)?.data.nombre}
          onConfirmar={handleConfirmarMultiplicidad}
          onCancelar={cancelarConexion}
        />
      )}

      {relacionAEditar && (
        <EditarRelacionModal
          relacion={relacionAEditar}
          onConfirmar={(cambios) => editarRelacion(relacionAEditar.id, cambios)}
          onCancelar={cancelarEdicionRelacion}
        />
      )}

      {claseAEliminarId && (
        <ConfirmModal
          titulo="Eliminar clase"
          mensaje={`¿Seguro que querés eliminar "${nodoAEliminar?.data.nombre}"? También se eliminarán sus relaciones.`}
          onConfirm={confirmarEliminarClase}
          onCancel={cancelarEliminarClase}
        />
      )}

      {modalAbierto === 'exportar' && (
        <ExportarModal
          onSeleccionarJson={() => {
            exportar('json')
            setModalAbierto(null)
          }}
          onSeleccionarPng={() => {
            exportarImagen()
            setModalAbierto(null)
          }}
          onSeleccionarXmi={() => {
            exportar('xmi')
            setModalAbierto(null)
          }}
          onCancelar={() => setModalAbierto(null)}
        />
      )}

      {modalAbierto === 'importar' && (
        <ImportarModal
          onArchivoSeleccionado={(archivo, formato) => {
            setImportacionPendiente({ archivo, formato })
            setModalAbierto(null)
          }}
          onSeleccionarImagen={() => {
            setModalAbierto(null)
            inputFotoRef.current?.click()
          }}
          onCancelar={() => setModalAbierto(null)}
        />
      )}

      {importacionPendiente && (
        <ConfirmModal
          titulo="Importar diagrama"
          mensaje={`¿Seguro que querés importar "${importacionPendiente.archivo.name}"? Se reemplazará todo el contenido actual del diagrama.`}
          onConfirm={() => {
            importar(importacionPendiente.archivo, importacionPendiente.formato)
            setImportacionPendiente(null)
          }}
          onCancel={() => setImportacionPendiente(null)}
        />
      )}
    </div>
  )
}

function Pizarra() {
  const { id } = useParams()
  const [diagrama, setDiagrama] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [proyectoNombre, setProyectoNombre] = useState(null)

  useEffect(() => {
    api
      .get(`/diagramas/proyecto/${id}`)
      .then(({ data }) => setDiagrama(data))
      .catch(() => setError('No se pudo cargar el diagrama.'))
      .finally(() => setCargando(false))
  }, [id])

  // Solo para el breadcrumb del header: si falla, se muestra sin el proyecto.
  useEffect(() => {
    api
      .get('/proyectos/mis-proyectos')
      .then(({ data }) => setProyectoNombre(data.find((p) => String(p.id) === id)?.nombre ?? null))
      .catch(() => setProyectoNombre(null))
  }, [id])

  if (cargando) {
    return <div className={`${styles.pagina} grid-bg`} />
  }

  if (error || !diagrama) {
    return <p className={styles.error}>{error ?? 'Diagrama no encontrado.'}</p>
  }

  return (
    <ReactFlowProvider key={diagrama.id}>
      <PizarraProvider contenidoInicial={diagrama.contenido}>
        <LienzoPizarra diagramaId={diagrama.id} diagramaNombre={diagrama.nombre} proyectoNombre={proyectoNombre} />
      </PizarraProvider>
    </ReactFlowProvider>
  )
}

export default Pizarra
