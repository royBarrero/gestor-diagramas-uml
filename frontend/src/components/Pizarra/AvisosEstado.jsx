import { useEffect, useState } from 'react'
import styles from './AvisosEstado.module.css'

const DURACION_MS = 6000

const clave = (aviso) => `${aviso.id}|${aviso.texto}|${aviso.detalle ?? ''}`

// Avisos de voz, foto, importación y exportación abajo al centro del lienzo.
// Los hooks que los originan no tienen forma de "limpiar" su estado, así que
// acá se recuerda qué avisos ya se cerraron; un mensaje distinto vuelve a
// aparecer. Los de resultado (ok/error) se cierran solos.
function AvisosEstado({ avisos }) {
  const [cerrados, setCerrados] = useState(() => new Set())

  const visibles = avisos.filter((aviso) => !cerrados.has(clave(aviso)))
  const clavesTemporales = visibles
    .filter((aviso) => aviso.tipo !== 'progreso')
    .map(clave)
    .join('\n')

  useEffect(() => {
    if (!clavesTemporales) return undefined
    const timeoutId = setTimeout(() => {
      setCerrados((actual) => new Set([...actual, ...clavesTemporales.split('\n')]))
    }, DURACION_MS)
    return () => clearTimeout(timeoutId)
  }, [clavesTemporales])

  function cerrar(aviso) {
    setCerrados((actual) => new Set([...actual, clave(aviso)]))
  }

  if (visibles.length === 0) return null

  return (
    <div className={styles.pila} aria-live="polite">
      {visibles.map((aviso) => (
        <div key={aviso.id} className={`${styles.aviso} ${styles[aviso.tipo]}`} title={aviso.detalle}>
          <span className={styles.punto} />
          <span className={styles.texto}>{aviso.texto}</span>
          <button type="button" className={styles.cerrar} onClick={() => cerrar(aviso)} title="Cerrar">
            <i className="ti ti-x" />
          </button>
        </div>
      ))}
    </div>
  )
}

export default AvisosEstado
