import { useCallback, useState } from 'react'
import { api } from '../services/api'
import { descargarBlob, mensajeDeErrorAxios, nombreDesdeContentDisposition } from '../utils/descargas'

// CU11: genera y descarga el backend Spring Boot del proyecto (solo admin).
export function useGenerarBackend() {
  const [estado, setEstado] = useState('inactivo') // inactivo | procesando | error
  const [mensaje, setMensaje] = useState(null)

  const generar = useCallback(async (proyectoId) => {
    setEstado('procesando')
    setMensaje(null)
    try {
      const respuesta = await api.get(`/proyectos/${proyectoId}/generar-backend`, {
        responseType: 'blob',
      })
      const nombre = nombreDesdeContentDisposition(respuesta.headers, 'backend.zip')
      descargarBlob(respuesta.data, nombre)
      setEstado('inactivo')
    } catch (err) {
      setEstado('error')
      setMensaje(await mensajeDeErrorAxios(err, 'No se pudo generar el backend.'))
    }
  }, [])

  return { estado, mensaje, generar }
}
