import { useEffect, useRef, useState } from 'react'
import styles from './ArchivoMenu.module.css'

// CU10: menú desplegable "Archivo" que agrupa Exportar/Importar en un solo
// botón, en vez de dos botones sueltos en el header.
function ArchivoMenu({ onExportar, onImportar }) {
  const [abierto, setAbierto] = useState(false)
  const contenedorRef = useRef(null)

  useEffect(() => {
    if (!abierto) return undefined
    function handleClickAfuera(event) {
      if (contenedorRef.current && !contenedorRef.current.contains(event.target)) {
        setAbierto(false)
      }
    }
    // fase de captura: el lienzo de React Flow frena la propagación de sus
    // clicks en la fase de burbujeo, así que un listener normal en `document`
    // nunca se entera de los clicks hechos sobre el lienzo.
    document.addEventListener('mousedown', handleClickAfuera, true)
    return () => document.removeEventListener('mousedown', handleClickAfuera, true)
  }, [abierto])

  return (
    <div className={styles.contenedor} ref={contenedorRef}>
      <button type="button" className={styles.trigger} onClick={() => setAbierto((a) => !a)} title="Archivo">
        <i className="ti ti-menu-2" /> Archivo <i className="ti ti-chevron-down" />
      </button>

      {abierto && (
        <div className={styles.menu}>
          <button
            type="button"
            className={styles.item}
            onClick={() => {
              setAbierto(false)
              onExportar()
            }}
          >
            <i className="ti ti-download" /> Exportar
          </button>
          <button
            type="button"
            className={styles.item}
            onClick={() => {
              setAbierto(false)
              onImportar()
            }}
          >
            <i className="ti ti-upload" /> Importar
          </button>
        </div>
      )}
    </div>
  )
}

export default ArchivoMenu
