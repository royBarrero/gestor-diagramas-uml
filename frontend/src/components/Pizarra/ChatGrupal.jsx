import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useChatGrupal } from '../../hooks/useChatGrupal'
import { colorPorUsuario } from '../../utils/avatar'
import MensajeFormateado from '../Asistente/MensajeFormateado'
import styles from './ChatGrupal.module.css'

const ALTO_MAX_INPUT = 120 // ~4 líneas
const MARGEN_PEGADO_ABAJO = 40
const ANCHO_PANEL = '360px'
const ANCHO_RIEL = '56px'

// Hoy solo la hora; otro día, también la fecha.
function formatearHora(iso) {
  const fecha = new Date(iso)
  const hora = fecha.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  if (fecha.toDateString() === new Date().toDateString()) return hora
  return `${fecha.toLocaleDateString([], { day: '2-digit', month: '2-digit' })} ${hora}`
}

// El split con grupo de captura deja las menciones en las posiciones impares.
function TextoConMenciones({ texto }) {
  return texto.split(/((?<!\w)@ia\b)/gi).map((parte, indice) =>
    indice % 2 === 1 ? (
      <span key={indice} className={styles.mencion}>
        {parte}
      </span>
    ) : (
      parte
    )
  )
}

function Mensaje({ mensaje, usuarioId }) {
  if (mensaje.tipo === 'sistema') {
    return <div className={styles.mensajeSistema}>{mensaje.texto}</div>
  }

  if (mensaje.tipo === 'agente') {
    return (
      <div className={styles.fila}>
        <span className={styles.avatarAgente} aria-hidden="true">
          <i className="ti ti-sparkles" />
        </span>
        <div className={styles.tarjetaAgente}>
          <div className={styles.encabezado}>
            <b className={styles.nombreAgente}>Agente IA</b>
            <span className={styles.hora}>{formatearHora(mensaje.created_at)}</span>
          </div>
          {mensaje.destino_id && (
            <div className={styles.destino}>
              Para{' '}
              <span className={styles.destinoNombre}>
                {mensaje.destino_id === usuarioId ? 'vos' : mensaje.destino_nombre}
              </span>
            </div>
          )}
          <MensajeFormateado texto={mensaje.texto} />
        </div>
      </div>
    )
  }

  return (
    <div className={styles.fila}>
      <span className={styles.avatar} style={{ background: colorPorUsuario(mensaje.autor_id) }} aria-hidden="true">
        {mensaje.autor_nombre?.[0]?.toUpperCase() ?? '?'}
      </span>
      <div className={styles.contenido}>
        <div className={styles.encabezado}>
          <b>{mensaje.autor_id === usuarioId ? 'Vos' : mensaje.autor_nombre}</b>
          <span className={styles.hora}>{formatearHora(mensaje.created_at)}</span>
        </div>
        <div className={styles.texto}>
          <TextoConMenciones texto={mensaje.texto} />
        </div>
      </div>
    </div>
  )
}

// CU15: chat del equipo, en una columna a la derecha del lienzo. Va fuera de
// canvasRef, así no sale en la exportación a PNG. La pizarra controla si está
// abierto porque las sugerencias de CU16 lo abren y resaltan un mensaje.
function ChatGrupal({ proyectoId, socket, estadoConexion, abierto, onCambiarAbierto, resaltar }) {
  const { usuario } = useAuth()
  const [texto, setTexto] = useState('')
  const {
    mensajes,
    noLeidos,
    agenteEscribiendo,
    hayAnteriores,
    errorCarga,
    errorEnvio,
    enviando,
    enviar,
    cargarAnteriores,
    reintentarCarga,
    marcarLeidos,
  } = useChatGrupal(proyectoId, socket, abierto)

  const listaRef = useRef(null)
  const inputRef = useRef(null)
  const pegadoAbajoRef = useRef(true)
  const alturaPreviaRef = useRef(null)
  const resaltadoRef = useRef(null)

  // El botón del asistente flotante se corre para no tapar el chat.
  useEffect(() => {
    const raiz = document.documentElement
    raiz.style.setProperty('--asistente-desplazamiento', abierto ? ANCHO_PANEL : ANCHO_RIEL)
    return () => raiz.style.removeProperty('--asistente-desplazamiento')
  }, [abierto])

  useEffect(() => {
    if (!abierto) return
    inputRef.current?.focus()
    marcarLeidos()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto])

  // Antes del efecto de scroll de abajo: al abrir, se arranca en el último mensaje.
  useLayoutEffect(() => {
    if (abierto) pegadoAbajoRef.current = true
  }, [abierto])

  // Al cargar mensajes viejos se conserva lo que se estaba leyendo; si no, baja
  // al último solo si el usuario ya estaba abajo.
  useLayoutEffect(() => {
    const lista = listaRef.current
    if (!lista) return
    if (alturaPreviaRef.current !== null) {
      lista.scrollTop += lista.scrollHeight - alturaPreviaRef.current
      alturaPreviaRef.current = null
    } else if (pegadoAbajoRef.current) {
      lista.scrollTop = lista.scrollHeight
    }
  }, [mensajes, agenteEscribiendo, abierto])

  // CU16: lleva a un mensaje y lo resalta. `resaltar` es un objeto nuevo en cada
  // pedido, para poder volver a resaltar el mismo mensaje.
  useEffect(() => {
    if (!resaltar || !abierto || resaltar === resaltadoRef.current) return
    const elemento = listaRef.current?.querySelector(`[data-mensaje-id="${resaltar.id}"]`)
    if (!elemento) return
    resaltadoRef.current = resaltar
    elemento.scrollIntoView({ block: 'center' })
    elemento.classList.remove(styles.resaltado)
    // Forzar el reflow permite reiniciar la animación si ya estaba resaltado.
    void elemento.offsetWidth
    elemento.classList.add(styles.resaltado)
  }, [resaltar, abierto, mensajes])

  function handleScroll() {
    const lista = listaRef.current
    pegadoAbajoRef.current = lista.scrollHeight - lista.scrollTop - lista.clientHeight < MARGEN_PEGADO_ABAJO
  }

  function ajustarAlto() {
    const input = inputRef.current
    if (!input) return
    input.style.height = 'auto'
    input.style.height = `${Math.min(input.scrollHeight, ALTO_MAX_INPUT)}px`
  }

  async function handleEnviar() {
    if (!texto.trim() || enviando) return
    pegadoAbajoRef.current = true
    if (await enviar(texto)) {
      setTexto('')
      requestAnimationFrame(() => {
        ajustarAlto()
        inputRef.current?.focus()
      })
    }
  }

  function handleTeclaInput(event) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      handleEnviar()
    }
  }

  function handleTeclaPanel(event) {
    if (event.key === 'Escape') onCambiarAbierto(false)
  }

  async function handleCargarAnteriores() {
    alturaPreviaRef.current = listaRef.current.scrollHeight
    if (!(await cargarAnteriores())) alturaPreviaRef.current = null
  }

  if (!abierto) {
    return (
      <nav className={styles.riel} aria-label="Chat del equipo (oculto)">
        <button
          type="button"
          className={styles.botonRiel}
          onClick={() => onCambiarAbierto(true)}
          title="Abrir chat"
          aria-label="Abrir chat"
        >
          <i className="ti ti-message-circle" />
          {noLeidos > 0 && (
            <span className={styles.contador} aria-label={`${noLeidos} sin leer`}>
              {noLeidos > 99 ? '99+' : noLeidos}
            </span>
          )}
        </button>
      </nav>
    )
  }

  return (
    <section className={styles.panel} aria-label="Chat del equipo" onKeyDown={handleTeclaPanel}>
      <header className={styles.header}>
        <span className={styles.titulo}>Chat</span>
        <button
          type="button"
          className={styles.botonIcono}
          onClick={() => onCambiarAbierto(false)}
          title="Ocultar chat"
          aria-label="Ocultar chat"
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

      <div className={styles.mensajes} ref={listaRef} onScroll={handleScroll} aria-live="polite">
        {hayAnteriores && (
          <button type="button" className={styles.botonSecundario} onClick={handleCargarAnteriores}>
            Cargar mensajes anteriores
          </button>
        )}

        {errorCarga && (
          <div className={styles.errorCarga}>
            No se pudieron cargar los mensajes.
            <button type="button" className={styles.botonSecundario} onClick={reintentarCarga}>
              Reintentar
            </button>
          </div>
        )}

        {mensajes.length === 0 && !errorCarga && (
          <p className={styles.vacio}>
            Todavía no hay mensajes. Escribí al equipo o mencioná <span className={styles.mencion}>@IA</span> para
            consultar al agente.
          </p>
        )}

        {mensajes.map((mensaje) => (
          <div key={mensaje.id} data-mensaje-id={mensaje.id} className={styles.contenedorMensaje}>
            <Mensaje mensaje={mensaje} usuarioId={usuario?.id} />
          </div>
        ))}

        {agenteEscribiendo && (
          <div className={styles.fila}>
            <span className={styles.avatarAgente} aria-hidden="true">
              <i className="ti ti-sparkles" />
            </span>
            <div className={styles.escribiendo} aria-label="El agente está escribiendo">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
      </div>

      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault()
          handleEnviar()
        }}
      >
        {errorEnvio && (
          <p className={styles.errorEnvio} role="alert">
            {errorEnvio}
          </p>
        )}
        <div className={styles.cajaInput}>
          <textarea
            ref={inputRef}
            rows={1}
            maxLength={2000}
            className={styles.input}
            placeholder="Escribí al equipo o mencioná @IA"
            value={texto}
            onChange={(event) => {
              setTexto(event.target.value)
              ajustarAlto()
            }}
            onKeyDown={handleTeclaInput}
            aria-label="Mensaje al equipo"
          />
          <button type="submit" className={styles.botonEnviar} disabled={enviando || !texto.trim()} aria-label="Enviar">
            <i className="ti ti-send" />
          </button>
        </div>
      </form>
    </section>
  )
}

export default ChatGrupal
