import { createContext, useCallback, useContext, useState } from 'react'
import { addEdge, useEdgesState, useNodesState } from '@xyflow/react'

const PizarraContext = createContext(null)

let contadorId = 0
function generarId(prefijo) {
  contadorId += 1
  return `${prefijo}-${Date.now()}-${contadorId}`
}

export function PizarraProvider({ contenidoInicial, children }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(contenidoInicial?.nodes ?? [])
  const [edges, setEdges, onEdgesChange] = useEdgesState(contenidoInicial?.edges ?? [])
  const [seleccionId, setSeleccionId] = useState(null)
  const [claseAEliminarId, setClaseAEliminarId] = useState(null)
  const [tipoRelacionActivo, setTipoRelacionActivo] = useState(null)
  const [origenConexionId, setOrigenConexionId] = useState(null)
  const [pendienteConexion, setPendienteConexion] = useState(null)
  const [panelClasesAbierto, setPanelClasesAbierto] = useState(true)
  const [relacionAEditar, setRelacionAEditar] = useState(null)

  const claseSeleccionada = nodes.find((n) => n.id === seleccionId) ?? null

  const reemplazarDiagrama = useCallback(
    (contenido) => {
      setNodes(contenido?.nodes ?? [])
      setEdges(contenido?.edges ?? [])
    },
    [setNodes, setEdges]
  )

  const seleccionarClase = useCallback((id) => setSeleccionId(id), [])

  const alternarPanelClases = useCallback(() => setPanelClasesAbierto((abierto) => !abierto), [])

  const agregarClase = useCallback(() => {
    const id = generarId('clase')
    const nuevoNodo = {
      id,
      type: 'clase',
      position: { x: 80 + Math.random() * 240, y: 80 + Math.random() * 200 },
      data: { nombre: 'NuevaClase', atributos: [], metodos: [] },
    }
    setNodes((nds) => [...nds, nuevoNodo])
    setSeleccionId(id)
    return id
  }, [setNodes])

  const eliminarClase = useCallback(
    (id) => {
      setNodes((nds) => nds.filter((n) => n.id !== id))
      setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
      setSeleccionId((actual) => (actual === id ? null : actual))
    },
    [setNodes, setEdges]
  )

  const renombrarClase = useCallback(
    (id, nombre) => {
      setNodes((nds) => nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, nombre } } : n)))
    },
    [setNodes]
  )

  const agregarCampoItem = useCallback(
    (claseId, campo) => {
      const nuevoId = generarId(campo)
      const nuevoItem =
        campo === 'atributos'
          ? { id: nuevoId, visibilidad: 'publico', tipo: '', texto: '' }
          : { id: nuevoId, visibilidad: 'publico', texto: '' }
      setNodes((nds) =>
        nds.map((n) =>
          n.id === claseId
            ? { ...n, data: { ...n.data, [campo]: [...n.data[campo], nuevoItem] } }
            : n
        )
      )
      return nuevoId
    },
    [setNodes]
  )

  const editarCampoItem = useCallback(
    (claseId, campo, itemId, cambios) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === claseId
            ? {
                ...n,
                data: {
                  ...n.data,
                  [campo]: n.data[campo].map((item) => (item.id === itemId ? { ...item, ...cambios } : item)),
                },
              }
            : n
        )
      )
    },
    [setNodes]
  )

  const eliminarCampoItem = useCallback(
    (claseId, campo, itemId) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === claseId
            ? { ...n, data: { ...n.data, [campo]: n.data[campo].filter((item) => item.id !== itemId) } }
            : n
        )
      )
    },
    [setNodes]
  )

  const moverCampoItem = useCallback(
    (claseId, campo, itemId, direccion) => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id !== claseId) return n
          const lista = [...n.data[campo]]
          const indice = lista.findIndex((item) => item.id === itemId)
          const nuevoIndice = indice + direccion
          if (indice === -1 || nuevoIndice < 0 || nuevoIndice >= lista.length) return n
          ;[lista[indice], lista[nuevoIndice]] = [lista[nuevoIndice], lista[indice]]
          return { ...n, data: { ...n.data, [campo]: lista } }
        })
      )
    },
    [setNodes]
  )

  const pedirEliminarClase = useCallback((id) => setClaseAEliminarId(id), [])
  const cancelarEliminarClase = useCallback(() => setClaseAEliminarId(null), [])
  const confirmarEliminarClase = useCallback(() => {
    if (claseAEliminarId) eliminarClase(claseAEliminarId)
    setClaseAEliminarId(null)
  }, [claseAEliminarId, eliminarClase])

  const iniciarConexion = useCallback(
    (connection) => {
      if (!connection.source || !connection.target || connection.source === connection.target) return
      setPendienteConexion({
        source: connection.source,
        target: connection.target,
        tipo: tipoRelacionActivo ?? 'asociacion',
      })
    },
    [tipoRelacionActivo]
  )

  const cancelarConexion = useCallback(() => setPendienteConexion(null), [])

  const seleccionarTipoRelacion = useCallback((tipo) => {
    setTipoRelacionActivo((actual) => (actual === tipo ? null : tipo))
    setOrigenConexionId(null)
  }, [])

  const cancelarOrigenConexion = useCallback(() => setOrigenConexionId(null), [])

  // Modo "click para conectar": con una herramienta de relación activa, el primer click
  // sobre una clase la marca como origen y el segundo abre el modal de multiplicidad.
  const manejarClickParaConectar = useCallback(
    (id) => {
      if (!tipoRelacionActivo) return
      if (!origenConexionId) {
        setOrigenConexionId(id)
        return
      }
      if (origenConexionId === id) {
        setOrigenConexionId(null)
        return
      }
      setPendienteConexion({ source: origenConexionId, target: id, tipo: tipoRelacionActivo })
      setOrigenConexionId(null)
    },
    [tipoRelacionActivo, origenConexionId]
  )

  const crearRelacion = useCallback(
    (source, target, tipo, multiplicidadOrigen, multiplicidadDestino, nombre) => {
      const nuevaRelacion = {
        id: generarId('rel'),
        source,
        target,
        type: 'relacion',
        data: { tipo, multiplicidadOrigen, multiplicidadDestino, nombre: nombre || undefined, estiloLinea: 'recta' },
      }
      setEdges((eds) => addEdge(nuevaRelacion, eds))
    },
    [setEdges]
  )

  const eliminarRelacion = useCallback(
    (edgeId) => {
      setEdges((eds) => eds.filter((e) => e.id !== edgeId))
    },
    [setEdges]
  )

  const cambiarEstiloLinea = useCallback(
    (edgeId, estilo) => {
      setEdges((eds) =>
        eds.map((e) => (e.id === edgeId ? { ...e, data: { ...e.data, estiloLinea: estilo } } : e))
      )
    },
    [setEdges]
  )

  const iniciarEdicionRelacion = useCallback((edge) => setRelacionAEditar(edge), [])
  const cancelarEdicionRelacion = useCallback(() => setRelacionAEditar(null), [])

  const editarRelacion = useCallback(
    (edgeId, cambios) => {
      setEdges((eds) => eds.map((e) => (e.id === edgeId ? { ...e, data: { ...e.data, ...cambios } } : e)))
      setRelacionAEditar(null)
    },
    [setEdges]
  )

  const value = {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    seleccionId,
    claseSeleccionada,
    seleccionarClase,
    agregarClase,
    renombrarClase,
    agregarCampoItem,
    editarCampoItem,
    eliminarCampoItem,
    moverCampoItem,
    pedirEliminarClase,
    claseAEliminarId,
    confirmarEliminarClase,
    cancelarEliminarClase,
    tipoRelacionActivo,
    seleccionarTipoRelacion,
    origenConexionId,
    manejarClickParaConectar,
    cancelarOrigenConexion,
    pendienteConexion,
    iniciarConexion,
    cancelarConexion,
    crearRelacion,
    eliminarRelacion,
    cambiarEstiloLinea,
    relacionAEditar,
    iniciarEdicionRelacion,
    cancelarEdicionRelacion,
    editarRelacion,
    reemplazarDiagrama,
    panelClasesAbierto,
    alternarPanelClases,
  }

  return <PizarraContext.Provider value={value}>{children}</PizarraContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePizarra() {
  const contexto = useContext(PizarraContext)
  if (!contexto) {
    throw new Error('usePizarra debe usarse dentro de PizarraProvider')
  }
  return contexto
}
