import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { addEdge, useEdgesState, useNodesState } from '@xyflow/react'
import {
  aplicarLado,
  calcularDiff,
  diffVacio,
  fusionarDiffs,
  quitarClasesAsociacion,
} from '../utils/historialDiagrama'

const PizarraContext = createContext(null)

const LIMITE_HISTORIAL = 100
// Ediciones seguidas con la misma clave (ej. tipear en el mismo atributo)
// dentro de esta ventana cuentan como un solo paso de deshacer.
const VENTANA_FUSION_MS = 1000

let contadorId = 0
function generarId(prefijo) {
  contadorId += 1
  return `${prefijo}-${Date.now()}-${contadorId}`
}

export function PizarraProvider({ contenidoInicial, children }) {
  const [nodes, setNodes, onNodesChangeBase] = useNodesState(contenidoInicial?.nodes ?? [])
  const [edges, setEdges, onEdgesChangeBase] = useEdgesState(contenidoInicial?.edges ?? [])
  const [seleccionId, setSeleccionId] = useState(null)
  const [claseAEliminarId, setClaseAEliminarId] = useState(null)
  const [tipoRelacionActivo, setTipoRelacionActivo] = useState(null)
  const [origenConexionId, setOrigenConexionId] = useState(null)
  const [pendienteConexion, setPendienteConexion] = useState(null)
  const [panelClasesAbierto, setPanelClasesAbierto] = useState(true)
  const [relacionAEditar, setRelacionAEditar] = useState(null)

  const claseSeleccionada = nodes.find((n) => n.id === seleccionId) ?? null

  // ---- Historial (deshacer/rehacer) ----
  // Cada acción local llama a `registrar` antes de modificar el estado; el
  // efecto de abajo compara contra el estado resultante y apila solo lo que
  // cambió. Los cambios remotos (colaboradores) no se registran.
  const nodesRef = useRef(nodes)
  const edgesRef = useRef(edges)
  const pendienteRef = useRef(null)
  const arrastreRef = useRef(null)
  const pilaDeshacerRef = useRef([])
  const pilaRehacerRef = useRef([])
  const ultimaEntradaRef = useRef(null)
  const [estadoHistorial, setEstadoHistorial] = useState({ puedeDeshacer: false, puedeRehacer: false })

  const actualizarEstadoHistorial = useCallback(() => {
    setEstadoHistorial({
      puedeDeshacer: pilaDeshacerRef.current.length > 0,
      puedeRehacer: pilaRehacerRef.current.length > 0,
    })
  }, [])

  const apilar = useCallback(
    (nodesAntes, edgesAntes, clave) => {
      const diff = calcularDiff(nodesAntes, edgesAntes, nodesRef.current, edgesRef.current)
      if (diffVacio(diff)) return

      const pila = pilaDeshacerRef.current
      const ultima = ultimaEntradaRef.current
      const ahora = Date.now()
      if (
        clave &&
        ultima &&
        ultima === pila[pila.length - 1] &&
        ultima.clave === clave &&
        ahora - ultima.tiempo < VENTANA_FUSION_MS
      ) {
        ultima.diff = fusionarDiffs(ultima.diff, diff)
        ultima.tiempo = ahora
        if (diffVacio(ultima.diff)) {
          pila.pop()
          ultimaEntradaRef.current = null
        }
      } else {
        const entrada = { diff, clave, tiempo: ahora }
        pila.push(entrada)
        if (pila.length > LIMITE_HISTORIAL) pila.shift()
        ultimaEntradaRef.current = entrada
      }
      pilaRehacerRef.current = []
      actualizarEstadoHistorial()
    },
    [actualizarEstadoHistorial]
  )

  useEffect(() => {
    nodesRef.current = nodes
    edgesRef.current = edges
    const pendiente = pendienteRef.current
    if (!pendiente) return
    pendienteRef.current = null
    apilar(pendiente.nodes, pendiente.edges, pendiente.clave)
  }, [nodes, edges, apilar])

  const registrar = useCallback((clave = null) => {
    // Si ya hay algo pendiente (dos setters en la misma acción), se conserva
    // la foto más vieja: es la de antes de la acción.
    if (!pendienteRef.current) {
      pendienteRef.current = { nodes: nodesRef.current, edges: edgesRef.current, clave }
    }
  }, [])

  const moverEnHistorial = useCallback(
    (desde, hacia, lado) => {
      const entrada = desde.current.pop()
      if (!entrada) return
      pendienteRef.current = null
      ultimaEntradaRef.current = null
      const resultado = aplicarLado(nodesRef.current, edgesRef.current, entrada.diff, lado)
      nodesRef.current = resultado.nodes
      edgesRef.current = resultado.edges
      setNodes(resultado.nodes)
      setEdges(resultado.edges)
      setSeleccionId((actual) => (resultado.nodes.some((n) => n.id === actual) ? actual : null))
      hacia.current.push(entrada)
      actualizarEstadoHistorial()
    },
    [setNodes, setEdges, actualizarEstadoHistorial]
  )

  const deshacer = useCallback(() => moverEnHistorial(pilaDeshacerRef, pilaRehacerRef, 'antes'), [moverEnHistorial])
  const rehacer = useCallback(() => moverEnHistorial(pilaRehacerRef, pilaDeshacerRef, 'despues'), [moverEnHistorial])

  // Arrastrar una clase genera muchos cambios de posición: se toma la foto al
  // empezar y se apila una sola entrada al soltar.
  const iniciarArrastre = useCallback(() => {
    arrastreRef.current = { nodes: nodesRef.current, edges: edgesRef.current }
  }, [])

  const finalizarArrastre = useCallback(() => {
    const inicio = arrastreRef.current
    arrastreRef.current = null
    if (inicio) apilar(inicio.nodes, inicio.edges, null)
  }, [apilar])

  // React Flow también borra nodos con la tecla Backspace, sin pasar por
  // eliminarClase: acá se cubre ese camino.
  const onNodesChange = useCallback(
    (cambios) => {
      const idsBorrados = cambios.filter((c) => c.type === 'remove').map((c) => c.id)
      if (idsBorrados.length) registrar()
      onNodesChangeBase(cambios)
      if (idsBorrados.length) setEdges((eds) => quitarClasesAsociacion(eds, idsBorrados))
    },
    [onNodesChangeBase, setEdges, registrar]
  )

  const onEdgesChange = useCallback(
    (cambios) => {
      if (cambios.some((c) => c.type === 'remove')) registrar()
      onEdgesChangeBase(cambios)
    },
    [onEdgesChangeBase, registrar]
  )

  // Cambios que llegan de afuera (colaboradores, recarga al conectar): no van
  // al historial.
  const reemplazarDiagrama = useCallback(
    (contenido) => {
      pendienteRef.current = null
      setNodes(contenido?.nodes ?? [])
      setEdges(contenido?.edges ?? [])
    },
    [setNodes, setEdges]
  )

  // Reemplazo hecho por el propio usuario (voz, foto, importación): se puede deshacer.
  const aplicarDiagramaLocal = useCallback(
    (contenido) => {
      registrar()
      setNodes(contenido?.nodes ?? [])
      setEdges(contenido?.edges ?? [])
    },
    [registrar, setNodes, setEdges]
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
    registrar()
    setNodes((nds) => [...nds, nuevoNodo])
    setSeleccionId(id)
    return id
  }, [setNodes, registrar])

  const eliminarClase = useCallback(
    (id) => {
      registrar()
      setNodes((nds) => nds.filter((n) => n.id !== id))
      setEdges((eds) => quitarClasesAsociacion(eds.filter((e) => e.source !== id && e.target !== id), [id]))
      setSeleccionId((actual) => (actual === id ? null : actual))
    },
    [setNodes, setEdges, registrar]
  )

  const renombrarClase = useCallback(
    (id, nombre) => {
      registrar(`nombre:${id}`)
      setNodes((nds) => nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, nombre } } : n)))
    },
    [setNodes, registrar]
  )

  const agregarCampoItem = useCallback(
    (claseId, campo) => {
      const nuevoId = generarId(campo)
      const nuevoItem =
        campo === 'atributos'
          ? { id: nuevoId, visibilidad: 'publico', tipo: '', texto: '' }
          : { id: nuevoId, visibilidad: 'publico', texto: '' }
      registrar()
      setNodes((nds) =>
        nds.map((n) =>
          n.id === claseId
            ? { ...n, data: { ...n.data, [campo]: [...n.data[campo], nuevoItem] } }
            : n
        )
      )
      return nuevoId
    },
    [setNodes, registrar]
  )

  const editarCampoItem = useCallback(
    (claseId, campo, itemId, cambios) => {
      registrar(`${campo}:${itemId}:${Object.keys(cambios).join(',')}`)
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
    [setNodes, registrar]
  )

  const eliminarCampoItem = useCallback(
    (claseId, campo, itemId) => {
      registrar()
      setNodes((nds) =>
        nds.map((n) =>
          n.id === claseId
            ? { ...n, data: { ...n.data, [campo]: n.data[campo].filter((item) => item.id !== itemId) } }
            : n
        )
      )
    },
    [setNodes, registrar]
  )

  const moverCampoItem = useCallback(
    (claseId, campo, itemId, direccion) => {
      registrar()
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
    [setNodes, registrar]
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
      registrar()
      setEdges((eds) => addEdge(nuevaRelacion, eds))
    },
    [setEdges, registrar]
  )

  const eliminarRelacion = useCallback(
    (edgeId) => {
      registrar()
      setEdges((eds) => eds.filter((e) => e.id !== edgeId))
    },
    [setEdges, registrar]
  )

  const cambiarEstiloLinea = useCallback(
    (edgeId, estilo) => {
      registrar()
      setEdges((eds) =>
        eds.map((e) => (e.id === edgeId ? { ...e, data: { ...e.data, estiloLinea: estilo } } : e))
      )
    },
    [setEdges, registrar]
  )

  const iniciarEdicionRelacion = useCallback((edge) => setRelacionAEditar(edge), [])
  const cancelarEdicionRelacion = useCallback(() => setRelacionAEditar(null), [])

  const editarRelacion = useCallback(
    (edgeId, cambios) => {
      registrar()
      setEdges((eds) => eds.map((e) => (e.id === edgeId ? { ...e, data: { ...e.data, ...cambios } } : e)))
      setRelacionAEditar(null)
    },
    [setEdges, registrar]
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
    aplicarDiagramaLocal,
    deshacer,
    rehacer,
    puedeDeshacer: estadoHistorial.puedeDeshacer,
    puedeRehacer: estadoHistorial.puedeRehacer,
    iniciarArrastre,
    finalizarArrastre,
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
