import { useCallback, useState } from 'react'
import { toPng } from 'html-to-image'
import { descargarBlob, slugificarNombre } from '../utils/descargas'

// CU10: exporta el lienzo a PNG 100% client-side (sin pasar por el backend).
export function useExportarImagen(elementoRef, nombreDiagrama) {
  const [estado, setEstado] = useState('inactivo') // inactivo | procesando | error

  const exportarImagen = useCallback(async () => {
    if (!elementoRef.current) return
    setEstado('procesando')
    try {
      const dataUrl = await toPng(elementoRef.current, {
        backgroundColor: '#0f1b2d',
        pixelRatio: 2,
        cacheBust: true,
      })
      const blob = await (await fetch(dataUrl)).blob()
      descargarBlob(blob, `${slugificarNombre(nombreDiagrama)}.png`)
      setEstado('inactivo')
    } catch {
      setEstado('error')
    }
  }, [elementoRef, nombreDiagrama])

  return { estado, exportarImagen }
}
