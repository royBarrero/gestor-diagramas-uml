import styles from './MensajeFormateado.module.css'

// Renderizador mínimo de Markdown para las respuestas del asistente.
// Arma elementos React (nada de innerHTML), así que el texto del modelo
// nunca se interpreta como HTML. Soporta párrafos, títulos (#), listas
// numeradas, viñetas, **negrita** y `código`.

const RE_NUMERADA = /^\s*(\d+)[.)]\s+(.*)$/
const RE_VINETA = /^\s*[-*•]\s+(.*)$/
const RE_TITULO = /^\s*#{1,6}\s+(.*)$/

function formatearEnLinea(texto, prefijoKey) {
  // Divide por **negrita** y `código`, manteniendo los separadores.
  const partes = texto.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean)
  return partes.map((parte, indice) => {
    const key = `${prefijoKey}-${indice}`
    if (parte.startsWith('**') && parte.endsWith('**') && parte.length > 4) {
      return <strong key={key}>{parte.slice(2, -2)}</strong>
    }
    if (parte.startsWith('`') && parte.endsWith('`') && parte.length > 2) {
      return <code key={key}>{parte.slice(1, -1)}</code>
    }
    return parte
  })
}

// Agrupa las líneas en bloques: párrafo, título, lista numerada o viñetas.
function parsearBloques(texto) {
  const bloques = []
  let parrafo = []

  function cerrarParrafo() {
    if (parrafo.length) {
      bloques.push({ tipo: 'parrafo', texto: parrafo.join(' ') })
      parrafo = []
    }
  }

  for (const linea of texto.replace(/\r\n/g, '\n').split('\n')) {
    const numerada = linea.match(RE_NUMERADA)
    const vineta = linea.match(RE_VINETA)
    const titulo = linea.match(RE_TITULO)
    const ultimo = bloques[bloques.length - 1]

    if (!linea.trim()) {
      cerrarParrafo()
    } else if (titulo) {
      cerrarParrafo()
      bloques.push({ tipo: 'titulo', texto: titulo[1] })
    } else if (numerada) {
      cerrarParrafo()
      if (ultimo?.tipo === 'numerada') ultimo.items.push(numerada[2])
      else bloques.push({ tipo: 'numerada', inicio: Number(numerada[1]), items: [numerada[2]] })
    } else if (vineta) {
      cerrarParrafo()
      if (ultimo?.tipo === 'vinetas') ultimo.items.push(vineta[1])
      else bloques.push({ tipo: 'vinetas', items: [vineta[1]] })
    } else if (!parrafo.length && (ultimo?.tipo === 'numerada' || ultimo?.tipo === 'vinetas') && /^\s+/.test(linea)) {
      // Línea indentada debajo de un ítem: continuación de ese ítem.
      ultimo.items[ultimo.items.length - 1] += ` ${linea.trim()}`
    } else {
      parrafo.push(linea.trim())
    }
  }
  cerrarParrafo()
  return bloques
}

function MensajeFormateado({ texto }) {
  const bloques = parsearBloques(texto)

  return (
    <div className={styles.mensaje}>
      {bloques.map((bloque, indice) => {
        const key = `b${indice}`
        if (bloque.tipo === 'titulo') {
          return (
            <p key={key} className={styles.titulo}>
              {formatearEnLinea(bloque.texto, key)}
            </p>
          )
        }
        if (bloque.tipo === 'numerada') {
          return (
            <ol key={key} className={styles.pasos} start={bloque.inicio}>
              {bloque.items.map((item, i) => (
                <li key={`${key}-${i}`}>
                  <span className={styles.numeroPaso} aria-hidden="true">
                    {bloque.inicio + i}
                  </span>
                  <span>{formatearEnLinea(item, `${key}-${i}`)}</span>
                </li>
              ))}
            </ol>
          )
        }
        if (bloque.tipo === 'vinetas') {
          return (
            <ul key={key} className={styles.vinetas}>
              {bloque.items.map((item, i) => (
                <li key={`${key}-${i}`}>{formatearEnLinea(item, `${key}-${i}`)}</li>
              ))}
            </ul>
          )
        }
        return <p key={key}>{formatearEnLinea(bloque.texto, key)}</p>
      })}
    </div>
  )
}

export default MensajeFormateado
