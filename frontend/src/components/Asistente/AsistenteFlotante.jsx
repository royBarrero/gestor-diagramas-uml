import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'
import { useAsistente } from '../../hooks/useAsistente'
import { sugerenciasPantalla } from '../../utils/contextoPantalla'
import MensajeFormateado from './MensajeFormateado'
import styles from './AsistenteFlotante.module.css'

const ALTO_MAX_INPUT = 120 // ~4 líneas

// CU13: agente asistente conversacional, accesible como widget flotante
// desde cualquier pantalla autenticada (se monta una sola vez en
// AuthenticatedLayout, no por página).
function AsistenteFlotante() {
  const { abierto, alternarPanel, mensajes, cargando, enviarPregunta, limpiarConversacion } = useAsistente()
  const { pathname } = useLocation()
  const [texto, setTexto] = useState('')
  const [expandido, setExpandido] = useState(false)
  const [copiado, setCopiado] = useState(null)
  const mensajesRef = useRef(null)
  const inputRef = useRef(null)

  // Baja solo al último mensaje cuando llega uno nuevo.
  useEffect(() => {
    const lista = mensajesRef.current
    if (lista) lista.scrollTop = lista.scrollHeight
  }, [mensajes, cargando, abierto])

  useEffect(() => {
    if (!abierto) return undefined
    inputRef.current?.focus()
    function handleTecla(event) {
      if (event.key === 'Escape') alternarPanel()
    }
    document.addEventListener('keydown', handleTecla)
    return () => document.removeEventListener('keydown', handleTecla)
  }, [abierto, alternarPanel])

  function ajustarAlto() {
    const input = inputRef.current
    if (!input) return
    input.style.height = 'auto'
    input.style.height = `${Math.min(input.scrollHeight, ALTO_MAX_INPUT)}px`
  }

  function enviar(pregunta) {
    if (!pregunta.trim() || cargando) return
    enviarPregunta(pregunta)
    setTexto('')
    requestAnimationFrame(ajustarAlto)
  }

  function handleSubmit(event) {
    event.preventDefault()
    enviar(texto)
  }

  function handleTeclaInput(event) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      enviar(texto)
    }
  }

  async function copiar(indice, contenido) {
    try {
      await navigator.clipboard.writeText(contenido)
      setCopiado(indice)
      setTimeout(() => setCopiado((actual) => (actual === indice ? null : actual)), 1500)
    } catch {
      // Sin permiso de portapapeles: no hacemos nada.
    }
  }

  return createPortal(
    <>
      {abierto && (
        <div
          className={`${styles.panel} ${expandido ? styles.panelExpandido : ''}`}
          role="dialog"
          aria-label="Asistente"
        >
          <header className={styles.header}>
            <span className={styles.iconoBot} aria-hidden="true">
              <i className="ti ti-message-chatbot" />
            </span>
            <div className={styles.headerTexto}>
              <span className={styles.titulo}>Asistente</span>
              <span className={styles.estado}>
                <span className={styles.puntoEstado} aria-hidden="true" /> Te ayudo a usar el sistema
              </span>
            </div>
            <div className={styles.headerAcciones}>
              {mensajes.length > 0 && (
                <button
                  type="button"
                  className={styles.botonIcono}
                  onClick={limpiarConversacion}
                  disabled={cargando}
                  title="Limpiar conversación"
                  aria-label="Limpiar conversación"
                >
                  <i className="ti ti-trash" />
                </button>
              )}
              <button
                type="button"
                className={`${styles.botonIcono} ${styles.soloEscritorio}`}
                onClick={() => setExpandido((e) => !e)}
                title={expandido ? 'Achicar' : 'Agrandar'}
                aria-label={expandido ? 'Achicar panel' : 'Agrandar panel'}
              >
                <i className={`ti ${expandido ? 'ti-arrows-minimize' : 'ti-arrows-maximize'}`} />
              </button>
              <button
                type="button"
                className={styles.botonIcono}
                onClick={alternarPanel}
                title="Cerrar"
                aria-label="Cerrar asistente"
              >
                <i className="ti ti-x" />
              </button>
            </div>
          </header>

          <div className={styles.mensajes} ref={mensajesRef} aria-live="polite">
            {mensajes.length === 0 && (
              <div className={styles.bienvenida}>
                <span className={styles.iconoBienvenida} aria-hidden="true">
                  <i className="ti ti-sparkles" />
                </span>
                <p className={styles.saludo}>¡Hola! ¿En qué te ayudo?</p>
                <p className={styles.saludoTexto}>
                  Preguntame cómo usar cualquier parte del sistema. Algunas ideas para esta pantalla:
                </p>
                <div className={styles.sugerencias}>
                  {sugerenciasPantalla(pathname).map((sugerencia) => (
                    <button
                      key={sugerencia}
                      type="button"
                      className={styles.sugerencia}
                      onClick={() => enviar(sugerencia)}
                    >
                      {sugerencia}
                      <i className="ti ti-arrow-up-right" aria-hidden="true" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {mensajes.map((mensaje, indice) =>
              mensaje.rol === 'usuario' ? (
                <div key={indice} className={styles.filaUsuario}>
                  <div className={styles.burbujaUsuario}>{mensaje.texto}</div>
                </div>
              ) : (
                <div key={indice} className={styles.filaAsistente}>
                  <span className={styles.avatarBot} aria-hidden="true">
                    <i className="ti ti-robot" />
                  </span>
                  <div className={styles.respuesta}>
                    <MensajeFormateado texto={mensaje.texto} />
                    <button
                      type="button"
                      className={styles.botonCopiar}
                      onClick={() => copiar(indice, mensaje.texto)}
                      aria-label="Copiar respuesta"
                    >
                      <i className={`ti ${copiado === indice ? 'ti-check' : 'ti-copy'}`} aria-hidden="true" />
                      {copiado === indice ? 'Copiado' : 'Copiar'}
                    </button>
                  </div>
                </div>
              )
            )}

            {cargando && (
              <div className={styles.filaAsistente}>
                <span className={styles.avatarBot} aria-hidden="true">
                  <i className="ti ti-robot" />
                </span>
                <div className={styles.escribiendo} aria-label="El asistente está escribiendo">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          <form className={styles.form} onSubmit={handleSubmit}>
            <div className={styles.cajaInput}>
              <textarea
                ref={inputRef}
                rows={1}
                className={styles.input}
                placeholder="Escribí tu pregunta..."
                value={texto}
                onChange={(event) => {
                  setTexto(event.target.value)
                  ajustarAlto()
                }}
                onKeyDown={handleTeclaInput}
                aria-label="Pregunta para el asistente"
              />
              <button
                type="submit"
                className={styles.botonEnviar}
                disabled={cargando || !texto.trim()}
                aria-label="Enviar"
              >
                <i className="ti ti-send" />
              </button>
            </div>
            <span className={styles.ayuda}>
              <kbd>Enter</kbd> para enviar · <kbd>Shift</kbd> + <kbd>Enter</kbd> para nueva línea
            </span>
          </form>
        </div>
      )}

      <button
        type="button"
        className={`${styles.botonFlotante} ${abierto ? styles.botonFlotanteAbierto : ''}`}
        onClick={alternarPanel}
        title={abierto ? 'Cerrar asistente' : 'Abrir asistente'}
        aria-label={abierto ? 'Cerrar asistente' : 'Abrir asistente'}
        aria-expanded={abierto}
      >
        <i className={abierto ? 'ti ti-x' : 'ti ti-message-chatbot'} />
      </button>
    </>,
    document.body
  )
}

export default AsistenteFlotante
