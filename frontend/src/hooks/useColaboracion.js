import { useEffect, useRef, useState } from 'react'
import { io } from 'socket.io-client'
import { api } from '../services/api'
import {
  calcularCambios,
  contenidoParaEnviar,
  firmasDe,
  fusionarRemoto,
  marcarSinConfirmar,
} from '../utils/sincronizacionDiagrama'
import { useDebouncedEffect } from './useDebouncedEffect'

export const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const MS_ENTRE_AVISOS_ACTIVIDAD = 10000

export function useColaboracion(diagramaId, { nodes, edges, reemplazarDiagrama, seleccionId }) {
  const [colaboradores, setColaboradores] = useState([])
  const [estadoConexion, setEstadoConexion] = useState('conectando')
  const [socket, setSocket] = useState(null)
  const socketRef = useRef(null)
  // Última versión sincronizada de cada elemento: lo que difiere de ahí es una
  // edición local que todavía hay que enviar.
  const baseRef = useRef(null)
  const localRef = useRef({ nodes, edges })
  const sinConfirmarRef = useRef(new Set())
  const seleccionRef = useRef(seleccionId)

  useEffect(() => {
    localRef.current = { nodes, edges }
  }, [nodes, edges])

  useEffect(() => {
    if (!diagramaId) return undefined

    baseRef.current = firmasDe(nodes, edges)

    function aplicarRemoto(contenido) {
      const fusion = fusionarRemoto(baseRef.current, localRef.current, contenido)
      baseRef.current = fusion.base
      // Sin esperar al render: el próximo mensaje puede llegar antes.
      localRef.current = { nodes: fusion.nodes, edges: fusion.edges }
      reemplazarDiagrama(localRef.current)
    }

    const conexion = io(SOCKET_URL, {
      auth: { token: localStorage.getItem('access_token') },
      query: { diagramaId },
    })
    socketRef.current = conexion
    // Se publica como estado para que useChatGrupal se suscriba: los efectos de
    // los componentes hijos corren antes que este, así que un ref no alcanza.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSocket(conexion)

    conexion.on('connect', () => {
      setEstadoConexion('conectado')
      // Cada conexión es un socket nuevo para el servidor: hay que volver a
      // decirle qué clase se está editando.
      if (seleccionRef.current) conexion.emit('seleccion', { claseId: seleccionRef.current })
      api.get(`/diagramas/${diagramaId}`).then(({ data }) => aplicarRemoto(data.contenido))
    })

    conexion.on('disconnect', () => {
      setEstadoConexion('desconectado')
      // La red pudo caerse antes de que el socket se enterara: lo que salió en ese
      // lapso no llegó, y se reenvía al reconectar.
      sinConfirmarRef.current.forEach((cambios) => marcarSinConfirmar(baseRef.current, cambios))
      sinConfirmarRef.current.clear()
    })
    conexion.io.on('reconnect_attempt', () => setEstadoConexion('reconectando'))
    // Si el servidor rechazó la conexión (por ejemplo, token vencido), socket.io
    // no reintenta solo; ante un fallo de red sigue con reconnect_attempt.
    conexion.on('connect_error', () => {
      if (!conexion.active) setEstadoConexion('rechazado')
    })

    conexion.on('colaboradores', (lista) => setColaboradores(lista))

    conexion.on('cambio_diagrama', aplicarRemoto)

    return () => {
      conexion.disconnect()
      socketRef.current = null
      setSocket(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [diagramaId])

  useEffect(() => {
    seleccionRef.current = seleccionId
    socketRef.current?.emit('seleccion', { claseId: seleccionId })
  }, [seleccionId])

  // CU17: el agente no toca una clase en uso, y escribir en un campo no le llega al
  // servidor hasta confirmarlo: sin esto, alguien tipeando figuraría inactivo.
  useEffect(() => {
    let ultimoAviso = 0
    function avisarActividad() {
      const ahora = Date.now()
      if (!seleccionRef.current || ahora - ultimoAviso < MS_ENTRE_AVISOS_ACTIVIDAD) return
      ultimoAviso = ahora
      socketRef.current?.emit('actividad')
    }
    window.addEventListener('keydown', avisarActividad, true)
    window.addEventListener('pointerdown', avisarActividad, true)
    return () => {
      window.removeEventListener('keydown', avisarActividad, true)
      window.removeEventListener('pointerdown', avisarActividad, true)
    }
  }, [])

  useDebouncedEffect(
    () => {
      // Sin conexión no se envía: la edición queda pendiente y, al reconectar, se
      // fusiona con lo que trae el servidor.
      if (!socketRef.current?.connected) return
      // Se compara el contenido, no "de dónde vino": así no se reenvía lo recibido
      // ni la selección, y una edición propia que cae en el mismo debounce que un
      // cambio remoto igual sale.
      const resultado = calcularCambios(baseRef.current, nodes, edges)
      if (!resultado) return
      baseRef.current = resultado.base
      sinConfirmarRef.current.add(resultado.cambios)
      socketRef.current.emit('cambio_diagrama', contenidoParaEnviar(nodes, edges, resultado.cambios), () =>
        sinConfirmarRef.current.delete(resultado.cambios)
      )
    },
    [nodes, edges],
    400
  )

  return { colaboradores, estadoConexion, socket }
}
