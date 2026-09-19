import { useCallback, useState } from 'react'
import { api } from '../services/api'
import { descargarBlob, nombreDesdeContentDisposition } from '../utils/descargas'

// CU10: descarga el diagrama actual en el formato elegido (generado en el backend).
export function useExportarDiagrama(diagramaId) {
  const [estado, setEstado] = useState('inactivo') // inactivo | procesando | error

  const exportar = useCallback(
    async (formato) => {
      setEstado('procesando')
      try {
        const respuesta = await api.get(`/diagramas/${diagramaId}/exportar`, {
          params: { formato },
          responseType: 'blob',
        })
        const nombre = nombreDesdeContentDisposition(respuesta.headers, `diagrama.${formato}`)
        descargarBlob(respuesta.data, nombre)
        setEstado('inactivo')
      } catch {
        setEstado('error')
      }
    },
    [diagramaId]
  )

  return { estado, exportar }
}
