import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Background, ReactFlow, ReactFlowProvider } from '@xyflow/react'
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
import PanelClases from '../../components/Pizarra/PanelClases'
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

function LienzoPizarra({ diagramaId, diagramaNombre }) {
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
    seleccionId,
    relacionAEditar,
    cancelarEdicionRelacion,
    editarRelacion,
  } = usePizarra()
  const { usuario } = useAuth()

  const [estadoGuardado, setEstadoGuardado] = useState('guardado')

  const { colaboradores, estadoConexion } = useColaboracion(diagramaId, {
    nodes,
    edges,
    reemplazarDiagrama,
    seleccionId,
  })
  const { estado: estadoVoz, mensaje: mensajeVoz, alternarGrabacion } = useComandoVoz(diagramaId, {
    onAplicado: reemplazarDiagrama,
  })
  const { estado: estadoFoto, mensaje: mensajeFoto, subirImagen } = useDigitalizacionImagen(diagramaId, {
    onAplicado: reemplazarDiagrama,
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
    onAplicado: reemplazarDiagrama,
  })

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

  function handleClickNodo(event, node) {
    seleccionarClase(node.id)
    manejarClickParaConectar(node.id)
  }

  return (
    <div className={styles.pagina}>
      <header className={styles.header}>
        <h1 className={styles.titulo}>Diagrama de Clases</h1>

        <div className={styles.headerDerecha}>
          {otrosColaboradores.length > 0 && (
            <div className={styles.colaboradores} title={otrosColaboradores.map((c) => c.nombre).join(', ')}>
              {otrosColaboradores.map((c) => (
                <span key={c.id} className={styles.colaboradorAvatar}>
                  {c.nombre?.[0]?.toUpperCase() ?? '?'}
                </span>
              ))}
            </div>
          )}

          {estadoConexion !== 'conectado' && (
            <span className={styles.estadoConexion}>
              {estadoConexion === 'reconectando' ? 'Reconectando...' : 'Sin conexión'}
            </span>
          )}

          <span className={styles.estado}>
            {estadoGuardado === 'guardando'
              ? 'Guardando...'
              : estadoGuardado === 'error'
                ? 'Error al guardar'
                : 'Guardado'}
          </span>

          <button
            type="button"
            className={`${styles.botonCircular} ${estadoVoz === 'grabando' ? styles.botonCircularActivo : ''}`}
            onClick={alternarGrabacion}
            disabled={estadoVoz === 'procesando'}
            title={estadoVoz === 'grabando' ? 'Detener grabación' : 'Comando de voz'}
          >
            <i className={`ti ${estadoVoz === 'grabando' ? 'ti-player-stop' : 'ti-microphone'}`} />
          </button>

          {estadoVoz !== 'inactivo' && estadoVoz !== 'grabando' && (
            <span className={styles.estadoVoz}>
              {estadoVoz === 'procesando' && 'Procesando comando...'}
              {estadoVoz === 'aplicado' && 'Comando aplicado ✓'}
              {estadoVoz === 'no_entendido' && `No entendí el comando: ${mensajeVoz}`}
              {estadoVoz === 'error_ia' && 'El asistente de voz no está disponible ahora.'}
              {estadoVoz === 'error' && mensajeVoz}
            </span>
          )}

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
            className={styles.botonCircular}
            onClick={() => inputFotoRef.current?.click()}
            disabled={estadoFoto === 'procesando'}
            title="Digitalizar diagrama por foto"
          >
            <i className="ti ti-camera" />
          </button>

          {estadoFoto !== 'inactivo' && (
            <span className={styles.estadoVoz}>
              {estadoFoto === 'procesando' && 'Analizando imagen...'}
              {estadoFoto === 'aplicado' && `Diagrama digitalizado ✓`}
              {estadoFoto === 'parcial' && `Digitalización parcial: ${mensajeFoto}`}
              {estadoFoto === 'fallido' && `No se pudo digitalizar: ${mensajeFoto}`}
              {estadoFoto === 'error_ia' && 'El servicio de visión no está disponible ahora.'}
              {estadoFoto === 'error' && mensajeFoto}
            </span>
          )}

          <ArchivoMenu onExportar={() => setModalAbierto('exportar')} onImportar={() => setModalAbierto('importar')} />

          {estadoExportar === 'error' && <span className={styles.estadoVoz}>No se pudo exportar el diagrama.</span>}
          {estadoExportarImagen === 'error' && <span className={styles.estadoVoz}>No se pudo exportar la imagen.</span>}

          {estadoImportar !== 'inactivo' && (
            <span className={styles.estadoVoz}>
              {estadoImportar === 'procesando' && 'Importando...'}
              {estadoImportar === 'aplicado' && 'Diagrama importado ✓'}
              {estadoImportar === 'formato_invalido' && `Archivo inválido: ${mensajeImportar}`}
              {estadoImportar === 'error' && mensajeImportar}
            </span>
          )}
        </div>
      </header>

      <div className={styles.cuerpo}>
        <PanelClases />

        <div className={styles.centro}>
          <Toolbar />
          <div className={`${styles.canvas} grid-bg`} ref={canvasRef}>
            <ErrorBoundaryLienzo>
              <ReactFlow
                nodes={nodesConPresencia}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={iniciarConexion}
                onNodeClick={handleClickNodo}
                onPaneClick={cancelarOrigenConexion}
                nodeTypes={tiposDeNodo}
                edgeTypes={tiposDeEdge}
                connectionMode="loose"
                fitView
              >
                <Background gap={24} color="rgba(255,255,255,0.04)" />
              </ReactFlow>
            </ErrorBoundaryLienzo>
          </div>
        </div>
      </div>

      {pendienteConexion && (
        <MultiplicidadModal onConfirmar={handleConfirmarMultiplicidad} onCancelar={cancelarConexion} />
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

  useEffect(() => {
    api
      .get(`/diagramas/proyecto/${id}`)
      .then(({ data }) => setDiagrama(data))
      .catch(() => setError('No se pudo cargar el diagrama.'))
      .finally(() => setCargando(false))
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
        <LienzoPizarra diagramaId={diagrama.id} diagramaNombre={diagrama.nombre} />
      </PizarraProvider>
    </ReactFlowProvider>
  )
}

export default Pizarra
