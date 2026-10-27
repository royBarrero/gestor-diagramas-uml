import { useEffect, useRef, useState } from 'react'
import { useGenerarBackend } from '../../hooks/useGenerarBackend'
import { useGenerarFrontend } from '../../hooks/useGenerarFrontend'
import { fechaRelativa } from '../../utils/fechaRelativa'
import styles from './GenerarCodigoMenu.module.css'

const ANCHO_PANEL = 300
const ALTO_PANEL_ESTIMADO = 250

// CU11/CU12: menú "Generar" en la tarjeta de proyecto, visible solo para el
// administrador — genera backend (Spring Boot) y frontend (Flutter, que
// requiere haber generado el backend antes).
function GenerarCodigoMenu({ proyectoId, backendGeneradoEn }) {
  const [abierto, setAbierto] = useState(false)
  const [posicion, setPosicion] = useState({ abajo: false, derecha: false })
  const [errorCerrado, setErrorCerrado] = useState(false)
  // Se marca al generar el backend desde acá, sin esperar a recargar la lista.
  const [backendGeneradoLocal, setBackendGeneradoLocal] = useState(null)
  const contenedorRef = useRef(null)
  const panelRef = useRef(null)
  const backend = useGenerarBackend()
  const frontend = useGenerarFrontend()

  const backendListoEn = backendGeneradoLocal ?? backendGeneradoEn
  const generandoBackend = backend.estado === 'procesando'
  const generandoFrontend = frontend.estado === 'procesando'
  const generando = generandoBackend || generandoFrontend
  const error = backend.estado === 'error' ? backend.mensaje : frontend.estado === 'error' ? frontend.mensaje : null

  useEffect(() => {
    if (!abierto) return undefined
    function handleClickAfuera(event) {
      if (contenedorRef.current && !contenedorRef.current.contains(event.target)) {
        setAbierto(false)
      }
    }
    function handleTecla(event) {
      if (event.key === 'Escape') setAbierto(false)
    }
    document.addEventListener('mousedown', handleClickAfuera)
    document.addEventListener('keydown', handleTecla)
    panelRef.current?.querySelector('[role="menuitem"]:not(:disabled)')?.focus()
    return () => {
      document.removeEventListener('mousedown', handleClickAfuera)
      document.removeEventListener('keydown', handleTecla)
    }
  }, [abierto])

  function abrirMenu() {
    if (!abierto && contenedorRef.current) {
      const rect = contenedorRef.current.getBoundingClientRect()
      setPosicion({
        abajo: rect.top < ALTO_PANEL_ESTIMADO + 16,
        derecha: rect.left + ANCHO_PANEL > window.innerWidth - 16,
      })
      setErrorCerrado(true)
    }
    setAbierto((a) => !a)
  }

  async function generarBackend() {
    setAbierto(false)
    setErrorCerrado(false)
    const ok = await backend.generar(proyectoId)
    if (ok) setBackendGeneradoLocal(new Date().toISOString())
  }

  function generarFrontend() {
    setAbierto(false)
    setErrorCerrado(false)
    frontend.generar(proyectoId)
  }

  const clasePanel = [
    styles.panel,
    posicion.abajo ? styles.panelAbajo : styles.panelArriba,
    posicion.derecha ? styles.panelDerecha : styles.panelIzquierda,
  ].join(' ')

  return (
    <div className={styles.contenedor} ref={contenedorRef}>
      <button
        type="button"
        className={styles.trigger}
        onClick={abrirMenu}
        disabled={generando}
        aria-haspopup="menu"
        aria-expanded={abierto}
      >
        {generando ? (
          <>
            <i className={`ti ti-loader-2 ${styles.spinner}`} aria-hidden="true" />
            {generandoBackend ? 'Backend...' : 'Frontend...'}
          </>
        ) : (
          <>
            <i className="ti ti-code" aria-hidden="true" />
            Generar
          </>
        )}
      </button>

      {abierto && (
        <div className={clasePanel} ref={panelRef} role="menu" aria-label="Generar código">
          <div className={styles.panelCabecera}>
            <span className={styles.panelTitulo}>Generar código</span>
            <span className={styles.panelSubtitulo}>Se descarga un .zip listo para abrir</span>
          </div>

          <button type="button" role="menuitem" className={`${styles.opcion} ${styles.opcionBackend}`} onClick={generarBackend}>
            <span className={`${styles.opcionIcono} ${styles.iconoBackend}`} aria-hidden="true">
              <i className="ti ti-server-2" />
            </span>
            <span className={styles.opcionTexto}>
              <span className={styles.opcionTitulo}>Backend</span>
              <span className={styles.opcionDescripcion}>Spring Boot · JPA · API REST</span>
              {backendListoEn && (
                <span className={styles.opcionEstado}>
                  <i className="ti ti-circle-check" aria-hidden="true" /> Generado{' '}
                  {fechaRelativa(backendListoEn).toLowerCase()}
                </span>
              )}
            </span>
            <i className={`ti ti-download ${styles.opcionAccion}`} aria-hidden="true" />
          </button>

          <button
            type="button"
            role="menuitem"
            className={`${styles.opcion} ${styles.opcionFrontend}`}
            onClick={generarFrontend}
            disabled={!backendListoEn}
          >
            <span className={`${styles.opcionIcono} ${styles.iconoFrontend}`} aria-hidden="true">
              <i className="ti ti-device-mobile" />
            </span>
            <span className={styles.opcionTexto}>
              <span className={styles.opcionTitulo}>Frontend</span>
              <span className={styles.opcionDescripcion}>App Flutter que consume tu backend</span>
              {!backendListoEn && (
                <span className={styles.opcionBloqueo}>
                  <i className="ti ti-lock" aria-hidden="true" /> Primero generá el backend
                </span>
              )}
            </span>
            <i className={`ti ${backendListoEn ? 'ti-download' : 'ti-lock'} ${styles.opcionAccion}`} aria-hidden="true" />
          </button>
        </div>
      )}

      {error && !errorCerrado && !abierto && (
        <div className={styles.burbujaError} role="alert">
          <i className="ti ti-alert-circle" aria-hidden="true" />
          <span>{error}</span>
          <button type="button" className={styles.cerrarError} onClick={() => setErrorCerrado(true)} aria-label="Cerrar">
            <i className="ti ti-x" />
          </button>
        </div>
      )}
    </div>
  )
}

export default GenerarCodigoMenu
