import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useAsistente } from '../../hooks/useAsistente'
import styles from './AsistenteFlotante.module.css'

// CU13: agente asistente conversacional, accesible como widget flotante
// desde cualquier pantalla autenticada (se monta una sola vez en
// AuthenticatedLayout, no por página).
function AsistenteFlotante() {
  const { abierto, alternarPanel, mensajes, cargando, enviarPregunta } = useAsistente()
  const [texto, setTexto] = useState('')

  const handleEnviar = (event) => {
    event.preventDefault()
    if (!texto.trim() || cargando) return
    enviarPregunta(texto)
    setTexto('')
  }

  return createPortal(
    <>
      {abierto && (
        <div className={styles.panel}>
          <div className={styles.header}>
            <span className={styles.titulo}>Asistente</span>
            <button type="button" className={styles.botonIcono} onClick={alternarPanel} title="Cerrar">
              <i className="ti ti-x" />
            </button>
          </div>

          <div className={styles.mensajes}>
            {mensajes.length === 0 && (
              <p className={styles.vacio}>¿En qué te puedo ayudar? Preguntame sobre cualquier funcionalidad del sistema.</p>
            )}
            {mensajes.map((mensaje, indice) => (
              <div
                key={indice}
                className={mensaje.rol === 'usuario' ? styles.burbujaUsuario : styles.burbujaAsistente}
              >
                {mensaje.texto}
              </div>
            ))}
            {cargando && <div className={styles.burbujaAsistente}>Pensando...</div>}
          </div>

          <form className={styles.form} onSubmit={handleEnviar}>
            <input
              type="text"
              className={styles.input}
              placeholder="Escribí tu pregunta..."
              value={texto}
              onChange={(event) => setTexto(event.target.value)}
              disabled={cargando}
            />
            <button type="submit" className={styles.botonEnviar} disabled={cargando || !texto.trim()}>
              <i className="ti ti-send" />
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        className={styles.botonFlotante}
        onClick={alternarPanel}
        title={abierto ? 'Cerrar asistente' : 'Abrir asistente'}
      >
        <i className={abierto ? 'ti ti-x' : 'ti ti-message-chatbot'} />
      </button>
    </>,
    document.body
  )
}

export default AsistenteFlotante
