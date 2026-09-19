import { useCallback, useState } from 'react'
import { api } from '../services/api'

// CU10: sube un archivo (JSON por ahora) y reemplaza el contenido del diagrama.
export function useImportarDiagrama(diagramaId, { onAplicado }) {
  // inactivo | procesando | aplicado | formato_invalido | error
  const [estado, setEstado] = useState('inactivo')
  const [mensaje, setMensaje] = useState(null)

  const importar = useCallback(
    async (archivo, formato) => {
      if (!archivo) return
      setEstado('procesando')
      setMensaje(null)
      const formData = new FormData()
      formData.append('archivo', archivo)
      formData.append('formato', formato)
      try {
        const { data } = await api.post(`/diagramas/${diagramaId}/importar`, formData)
        setMensaje(data.mensaje)
        setEstado(data.estado)
        if (data.estado === 'aplicado' && data.contenido) {
          onAplicado(data.contenido)
        }
      } catch {
        setEstado('error')
        setMensaje('No se pudo enviar el archivo. Intentá de nuevo.')
      }
    },
    [diagramaId, onAplicado]
  )

  return { estado, mensaje, importar }
}
