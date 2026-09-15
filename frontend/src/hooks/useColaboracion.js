import { useEffect, useRef, useState } from 'react'
import { io } from 'socket.io-client'
import { api } from '../services/api'
import { useDebouncedEffect } from './useDebouncedEffect'

const SOCKET_URL = 'http://localhost:8000'

export function useColaboracion(diagramaId, { nodes, edges, reemplazarDiagrama, seleccionId }) {
  const [colaboradores, setColaboradores] = useState([])
  const [estadoConexion, setEstadoConexion] = useState('conectando')
  const socketRef = useRef(null)
  const aplicandoRemotoRef = useRef(false)
  const primeraEmisionRef = useRef(true)

  useEffect(() => {
    if (!diagramaId) return undefined

    primeraEmisionRef.current = true
    const socket = io(SOCKET_URL, {
      auth: { token: localStorage.getItem('access_token') },
      query: { diagramaId },
    })
    socketRef.current = socket

    socket.on('connect', () => {
      setEstadoConexion('conectado')
      api.get(`/diagramas/${diagramaId}`).then(({ data }) => {
        aplicandoRemotoRef.current = true
        reemplazarDiagrama(data.contenido)
      })
    })

    socket.on('disconnect', () => setEstadoConexion('desconectado'))
    socket.io.on('reconnect_attempt', () => setEstadoConexion('reconectando'))

    socket.on('colaboradores', (lista) => setColaboradores(lista))

    socket.on('cambio_diagrama', (contenido) => {
      aplicandoRemotoRef.current = true
      reemplazarDiagrama(contenido)
    })

    return () => {
      socket.disconnect()
      socketRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [diagramaId])

  useEffect(() => {
    socketRef.current?.emit('seleccion', { claseId: seleccionId })
  }, [seleccionId])

  useDebouncedEffect(
    () => {
      if (primeraEmisionRef.current) {
        primeraEmisionRef.current = false
        return
      }
      if (aplicandoRemotoRef.current) {
        aplicandoRemotoRef.current = false
        return
      }
      socketRef.current?.emit('cambio_diagrama', { nodes, edges })
    },
    [nodes, edges],
    400
  )

  return { colaboradores, estadoConexion }
}
