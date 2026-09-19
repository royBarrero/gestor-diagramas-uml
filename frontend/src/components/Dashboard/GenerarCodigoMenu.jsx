import { useEffect, useRef, useState } from 'react'
import { useGenerarBackend } from '../../hooks/useGenerarBackend'
import { useGenerarFrontend } from '../../hooks/useGenerarFrontend'
import styles from './GenerarCodigoMenu.module.css'

// CU11/CU12: menú desplegable "Generar código" en la tarjeta de proyecto,
// visible solo para el administrador — genera backend (Spring Boot) y
// frontend (Flutter, requiere haber generado el backend antes).
function GenerarCodigoMenu({ proyectoId }) {
  const [abierto, setAbierto] = useState(false)
  const contenedorRef = useRef(null)
  const backend = useGenerarBackend()
  const frontend = useGenerarFrontend()

  const generando = backend.estado === 'procesando' || frontend.estado === 'procesando'
  const error = backend.estado === 'error' ? backend.mensaje : frontend.estado === 'error' ? frontend.mensaje : null

  useEffect(() => {
    if (!abierto) return undefined
    function handleClickAfuera(event) {
      if (contenedorRef.current && !contenedorRef.current.contains(event.target)) {
        setAbierto(false)
      }
    }
    document.addEventListener('mousedown', handleClickAfuera)
    return () => document.removeEventListener('mousedown', handleClickAfuera)
  }, [abierto])

  function abrirMenu(event) {
    event.preventDefault()
    event.stopPropagation()
    setAbierto((a) => !a)
  }

  function seleccionar(event, generar) {
    event.preventDefault()
    event.stopPropagation()
    setAbierto(false)
    generar(proyectoId)
  }

  return (
    <div className={styles.contenedor} ref={contenedorRef}>
      <button type="button" className={styles.trigger} onClick={abrirMenu} disabled={generando}>
        <i className="ti ti-code" />
        {generando ? 'Generando...' : 'Generar código'}
      </button>

      {abierto && (
        <div className={styles.menu}>
          <button type="button" className={styles.item} onClick={(event) => seleccionar(event, backend.generar)}>
            <i className="ti ti-server-2" /> Backend (Spring Boot)
          </button>
          <button type="button" className={styles.item} onClick={(event) => seleccionar(event, frontend.generar)}>
            <i className="ti ti-device-mobile" /> Frontend (Flutter)
          </button>
        </div>
      )}

      {error && <p className={styles.error}>{error}</p>}
    </div>
  )
}

export default GenerarCodigoMenu
