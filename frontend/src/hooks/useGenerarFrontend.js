import { useCallback, useState } from 'react'
import { api } from '../services/api'
import { descargarBlob, mensajeDeErrorAxios, nombreDesdeContentDisposition } from '../utils/descargas'

// CU12: genera y descarga el frontend Flutter del proyecto (solo admin,
// requiere haber generado el backend antes — ver Proyecto.backend_generado_en).
export function useGenerarFrontend() {
  const [estado, setEstado] = useState('inactivo') // inactivo | procesando | error
  const [mensaje, setMensaje] = useState(null)

  const generar = useCallback(async (proyectoId) => {
    setEstado('procesando')
    setMensaje(null)
    try {
      const respuesta = await api.get(`/proyectos/${proyectoId}/generar-frontend`, {
        responseType: 'blob',
      })
      const nombre = nombreDesdeContentDisposition(respuesta.headers, 'frontend.zip')
      descargarBlob(respuesta.data, nombre)
      setEstado('inactivo')
    } catch (err) {
      setEstado('error')
      setMensaje(await mensajeDeErrorAxios(err, 'No se pudo generar el frontend.'))
    }
  }, [])

  return { estado, mensaje, generar }
}
