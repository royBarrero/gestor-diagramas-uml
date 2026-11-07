import { useEffect } from 'react'
import { useChatGrupal } from '../../hooks/useChatGrupal'
import { useHistorialCambios } from '../../hooks/useHistorialCambios'
import ChatGrupal from './ChatGrupal'
import HistorialCambios from './HistorialCambios'
import styles from './PanelLateral.module.css'

const ANCHO_PANEL = '360px'
const ANCHO_RIEL = '56px'

// Columna a la derecha del lienzo, con el chat del equipo (CU15) y el historial de
// cambios (CU18). Va fuera de canvasRef, así no sale en la exportación a PNG. La pizarra
// controla qué muestra porque las sugerencias de CU16 abren el chat. Las dos pestañas
// quedan montadas: no se pierde lo escrito ni dónde se estaba leyendo.
function PanelLateral({
  proyectoId,
  socket,
  estadoConexion,
  abierto,
  pestana,
  onCambiarAbierto,
  onCambiarPestana,
  resaltar,
  nodos,
  onIrAClase,
}) {
  const chatVisible = abierto && pestana === 'chat'
  const historialVisible = abierto && pestana === 'historial'
  const chat = useChatGrupal(proyectoId, socket, chatVisible)
  const historial = useHistorialCambios(proyectoId, socket, historialVisible)

  // El botón del asistente flotante se corre para no tapar el panel.
  useEffect(() => {
    const raiz = document.documentElement
    raiz.style.setProperty('--asistente-desplazamiento', abierto ? ANCHO_PANEL : ANCHO_RIEL)
    return () => raiz.style.removeProperty('--asistente-desplazamiento')
  }, [abierto])

  function abrir(destino) {
    onCambiarPestana(destino)
    onCambiarAbierto(true)
  }

  function handleTecla(event) {
    if (event.key === 'Escape') onCambiarAbierto(false)
  }

  function clasePestana(nombre) {
    return `${styles.pestana} ${pestana === nombre ? styles.pestanaActiva : ''}`
  }

  return (
    <>
      {!abierto && (
        <nav className={styles.riel} aria-label="Panel del equipo (oculto)">
          <button
            type="button"
            className={styles.botonRiel}
            onClick={() => abrir('chat')}
            title="Abrir chat"
            aria-label="Abrir chat"
          >
            <i className="ti ti-message-circle" />
            {chat.noLeidos > 0 && (
              <span className={styles.contador} aria-label={`${chat.noLeidos} sin leer`}>
                {chat.noLeidos > 99 ? '99+' : chat.noLeidos}
              </span>
            )}
          </button>
          <button
            type="button"
            className={styles.botonRiel}
            onClick={() => abrir('historial')}
            title="Abrir historial"
            aria-label="Abrir historial"
          >
            <i className="ti ti-history" />
          </button>
        </nav>
      )}

      <section
        className={`${styles.panel} ${abierto ? '' : styles.oculto}`}
        aria-label="Panel del equipo"
        onKeyDown={handleTecla}
      >
        <header className={styles.header}>
          <div className={styles.pestanas} role="tablist" aria-label="Contenido del panel">
            <button
              type="button"
              role="tab"
              aria-selected={pestana === 'chat'}
              className={clasePestana('chat')}
              onClick={() => onCambiarPestana('chat')}
            >
              Chat
              {pestana !== 'chat' && chat.noLeidos > 0 && (
                <span className={styles.contadorPestana} aria-label={`${chat.noLeidos} sin leer`}>
                  {chat.noLeidos > 99 ? '99+' : chat.noLeidos}
                </span>
              )}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={pestana === 'historial'}
              className={clasePestana('historial')}
              onClick={() => onCambiarPestana('historial')}
            >
              Historial
            </button>
          </div>
          <button
            type="button"
            className={styles.botonIcono}
            onClick={() => onCambiarAbierto(false)}
            title="Ocultar panel"
            aria-label="Ocultar panel"
          >
            <i className="ti ti-layout-sidebar-right-collapse" />
          </button>
        </header>

        {['desconectado', 'reconectando'].includes(estadoConexion) && (
          <div className={styles.aviso} role="status">
            <i className="ti ti-wifi-off" aria-hidden="true" /> Sin conexión, reintentando…
          </div>
        )}
        {estadoConexion === 'rechazado' && (
          <div className={styles.aviso} role="status">
            <i className="ti ti-wifi-off" aria-hidden="true" /> Sin conexión. Recargá la página o volvé a iniciar sesión.
          </div>
        )}

        <div className={`${styles.contenido} ${chatVisible ? '' : styles.oculto}`} role="tabpanel">
          <ChatGrupal chat={chat} visible={chatVisible} resaltar={resaltar} />
        </div>
        <div className={`${styles.contenido} ${historialVisible ? '' : styles.oculto}`} role="tabpanel">
          <HistorialCambios historial={historial} nodos={nodos} visible={historialVisible} onIrAClase={onIrAClase} />
        </div>
      </section>
    </>
  )
}

export default PanelLateral
