import { useCallback, useState } from 'react'
import { api } from '../services/api'

// CU09: sube/fotografía una imagen de un diagrama en papel, la manda al
// backend para que la reconozca (visión por computadora) y aplica el
// resultado (fusionado con lo que ya había) sobre el diagrama.
export function useDigitalizacionImagen(diagramaId, { onAplicado }) {
  // inactivo | procesando | aplicado | parcial | fallido | error_ia | error
  const [estado, setEstado] = useState('inactivo')
  const [mensaje, setMensaje] = useState(null)

  const subirImagen = useCallback(
    async (archivo) => {
      if (!archivo) return
      setEstado('procesando')
      setMensaje(null)
      const formData = new FormData()
      formData.append('imagen', archivo)
      try {
        const { data } = await api.post(`/diagramas/${diagramaId}/digitalizar-imagen`, formData)
        setMensaje(data.mensaje)
        setEstado(data.estado)
        if ((data.estado === 'aplicado' || data.estado === 'parcial') && data.contenido) {
          onAplicado(data.contenido)
        }
      } catch {
        setEstado('error')
        setMensaje('No se pudo enviar la imagen. Intentá de nuevo.')
      }
    },
    [diagramaId, onAplicado]
  )

  return { estado, mensaje, subirImagen }
}
