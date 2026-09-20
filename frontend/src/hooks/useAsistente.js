import { useCallback, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../services/api'
import { contextoPantalla } from '../utils/contextoPantalla'

// CU13: chat flotante del agente asistente, disponible desde cualquier
// pantalla autenticada. El historial vive solo en memoria del componente —
// no se persiste en el backend, se pierde al recargar la página.
export function useAsistente() {
  const [abierto, setAbierto] = useState(false)
  const [mensajes, setMensajes] = useState([])
  const [cargando, setCargando] = useState(false)
  const { pathname } = useLocation()

  const alternarPanel = useCallback(() => {
    setAbierto((valor) => !valor)
  }, [])

  const enviarPregunta = useCallback(
    async (texto) => {
      const pregunta = texto.trim()
      if (!pregunta || cargando) return

      const historial = mensajes
      setMensajes((actuales) => [...actuales, { rol: 'usuario', texto: pregunta }])
      setCargando(true)
      try {
        const { data } = await api.post('/asistente/preguntar', {
          pregunta,
          contexto_pantalla: contextoPantalla(pathname),
          historial,
        })
        const textoRespuesta =
          data.estado === 'respondido'
            ? data.respuesta
            : data.mensaje || 'El asistente no está disponible en este momento.'
        setMensajes((actuales) => [...actuales, { rol: 'asistente', texto: textoRespuesta }])
      } catch {
        setMensajes((actuales) => [
          ...actuales,
          { rol: 'asistente', texto: 'No se pudo contactar al asistente. Probá de nuevo en un momento.' },
        ])
      } finally {
        setCargando(false)
      }
    },
    [mensajes, cargando, pathname]
  )

  return { abierto, alternarPanel, mensajes, cargando, enviarPregunta }
}
