import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Background, ReactFlow, ReactFlowProvider } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api } from '../../services/api'
import { PizarraProvider, usePizarra } from '../../contexts/PizarraContext'
import { useDebouncedEffect } from '../../hooks/useDebouncedEffect'
import ClaseNode from '../../components/Pizarra/ClaseNode'
import RelacionEdge from '../../components/Pizarra/RelacionEdge'
import Toolbar from '../../components/Pizarra/Toolbar'
import PanelClases from '../../components/Pizarra/PanelClases'
import MultiplicidadModal from '../../components/Pizarra/MultiplicidadModal'
import ConfirmModal from '../../components/ConfirmModal/ConfirmModal'
import ErrorBoundaryLienzo from '../../components/Pizarra/ErrorBoundaryLienzo'
import styles from './Pizarra.module.css'

const tiposDeNodo = { clase: ClaseNode }
const tiposDeEdge = { relacion: RelacionEdge }

function LienzoPizarra({ diagramaId }) {
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
  } = usePizarra()

  const [estadoGuardado, setEstadoGuardado] = useState('guardado')
  const primeraCarga = useRef(true)

  useDebouncedEffect(
    () => {
      if (primeraCarga.current) {
        primeraCarga.current = false
        return
      }
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
        <span className={styles.estado}>
          {estadoGuardado === 'guardando'
            ? 'Guardando...'
            : estadoGuardado === 'error'
              ? 'Error al guardar'
              : 'Guardado'}
        </span>
      </header>

      <div className={styles.cuerpo}>
        <PanelClases />

        <div className={styles.centro}>
          <Toolbar />
          <div className={`${styles.canvas} grid-bg`}>
            <ErrorBoundaryLienzo>
              <ReactFlow
                nodes={nodes}
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

      {claseAEliminarId && (
        <ConfirmModal
          titulo="Eliminar clase"
          mensaje={`¿Seguro que querés eliminar "${nodoAEliminar?.data.nombre}"? También se eliminarán sus relaciones.`}
          onConfirm={confirmarEliminarClase}
          onCancel={cancelarEliminarClase}
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
        <LienzoPizarra diagramaId={diagrama.id} />
      </PizarraProvider>
    </ReactFlowProvider>
  )
}

export default Pizarra
