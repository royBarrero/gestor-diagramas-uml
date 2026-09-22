import { useCallback, useRef, useState } from 'react'
import { api } from '../services/api'

// CU08: captura un comando de voz (push-to-talk), lo manda al backend para
// que lo transcriba/interprete, y aplica el resultado sobre el diagrama.
export function useComandoVoz(diagramaId, { onAplicado }) {
  // inactivo | grabando | procesando | aplicado | no_entendido | error_ia | error
  const [estado, setEstado] = useState('inactivo')
  const [mensaje, setMensaje] = useState(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])

  const enviarAudio = useCallback(
    async (blob) => {
      setEstado('procesando')
      const formData = new FormData()
      formData.append('audio', blob, 'comando.webm')
      try {
        const { data } = await api.post(`/diagramas/${diagramaId}/comando-voz`, formData)
        setMensaje(data.mensaje)
        setEstado(data.estado)
        if (data.estado === 'aplicado' && data.contenido) {
          onAplicado(data.contenido)
        }
      } catch {
        setEstado('error')
        setMensaje('No se pudo enviar el audio. Intentá de nuevo.')
      }
    },
    [diagramaId, onAplicado]
  )

  const iniciarGrabacion = useCallback(async () => {
    // navigator.mediaDevices solo existe en contextos seguros (HTTPS o
    // localhost). Sin esto, accederlo revienta con un TypeError que un catch
    // genérico confundiría con un permiso denegado.
    if (!navigator.mediaDevices?.getUserMedia) {
      setEstado('error')
      setMensaje('El comando de voz requiere una conexión segura (HTTPS). Este sitio se está sirviendo sin HTTPS.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []

      mediaRecorder.ondataavailable = (evento) => {
        if (evento.data.size > 0) chunksRef.current.push(evento.data)
      }
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        enviarAudio(new Blob(chunksRef.current, { type: 'audio/webm' }))
      }

      mediaRecorder.start()
      mediaRecorderRef.current = mediaRecorder
      setMensaje(null)
      setEstado('grabando')
    } catch (error) {
      setEstado('error')
      if (error.name === 'NotAllowedError' || error.name === 'SecurityError') {
        setMensaje('No se pudo acceder al micrófono. Revisá los permisos del navegador.')
      } else if (error.name === 'NotFoundError') {
        setMensaje('No se encontró ningún micrófono disponible.')
      } else {
        setMensaje('No se pudo acceder al micrófono. Intentá de nuevo.')
      }
    }
  }, [enviarAudio])

  const detenerGrabacion = useCallback(() => {
    mediaRecorderRef.current?.stop()
  }, [])

  const alternarGrabacion = useCallback(() => {
    if (estado === 'grabando') {
      detenerGrabacion()
    } else {
      iniciarGrabacion()
    }
  }, [estado, detenerGrabacion, iniciarGrabacion])

  return { estado, mensaje, alternarGrabacion }
}
