export function nombreDesdeContentDisposition(headers, fallback) {
  const disposicion = headers?.['content-disposition'] || ''
  const match = disposicion.match(/filename="?([^"]+)"?/)
  return match ? match[1] : fallback
}

// Cuando la petición usa responseType: 'blob' y el backend responde un error
// (ej. 400), axios igual entrega el body como Blob en vez de JSON parseado
// — hay que leerlo a mano para mostrar el mensaje real del backend.
export async function mensajeDeErrorAxios(err, fallback) {
  const data = err.response?.data
  if (data instanceof Blob && data.type === 'application/json') {
    try {
      const texto = await data.text()
      return JSON.parse(texto)?.detail ?? fallback
    } catch {
      return fallback
    }
  }
  return data?.detail ?? fallback
}

export function descargarBlob(blob, nombreArchivo) {
  const url = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombreArchivo
  enlace.click()
  URL.revokeObjectURL(url)
}

// Replica en JS de `nombre_archivo_descarga` (backend/app/services/exportacion_diagrama.py),
// para que el PNG (generado client-side) se nombre igual que el JSON (generado en backend).
export function slugificarNombre(nombre) {
  const slug = (nombre || 'diagrama')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return slug || 'diagrama'
}
