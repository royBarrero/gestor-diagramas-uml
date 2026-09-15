import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  getSmoothStepPath,
  getStraightPath,
  Position,
  useInternalNode,
} from '@xyflow/react'
import { usePizarra } from '../../contexts/PizarraContext'
import styles from './RelacionEdge.module.css'

const LARGO_FORMA = 16
const ANCHO_FORMA = 10
const LARGO_FLECHA = 12
const ANCHO_FLECHA = 8

const OPCIONES_ESTILO = [
  { valor: 'recta', etiqueta: 'Recta', icono: 'ti-line' },
  { valor: 'curva', etiqueta: 'Curva', icono: 'ti-vector-spline' },
  { valor: 'ortogonal', etiqueta: 'En L', icono: 'ti-corner-down-right' },
]

// "Edge flotante": en vez de depender de un handle fijo elegido al crear la
// relación (que queda desactualizado si después movés las clases), calculamos
// en cada render el punto donde la línea centro-a-centro cruza el borde del
// nodo. Como usa la posición actual de ambos nodos, se recalcula solo cuando
// cualquiera de los dos se mueve. Algoritmo estándar de "floating edges" de
// React Flow.
function interseccionConBorde(nodoBorde, nodoObjetivo) {
  const { width, height } = nodoBorde.measured
  const posBorde = nodoBorde.internals.positionAbsolute
  const posObjetivo = nodoObjetivo.internals.positionAbsolute

  const w = width / 2
  const h = height / 2
  const x2 = posBorde.x + w
  const y2 = posBorde.y + h
  const x1 = posObjetivo.x + nodoObjetivo.measured.width / 2
  const y1 = posObjetivo.y + nodoObjetivo.measured.height / 2

  const xx1 = (x1 - x2) / (2 * w) - (y1 - y2) / (2 * h)
  const yy1 = (x1 - x2) / (2 * w) + (y1 - y2) / (2 * h)
  const a = 1 / (Math.abs(xx1) + Math.abs(yy1) || 1)
  const xx3 = a * xx1
  const yy3 = a * yy1

  return {
    x: w * (xx3 + yy3) + x2,
    y: h * (-xx3 + yy3) + y2,
  }
}

// Para curva/ortogonal anclamos en el lado cardinal (arriba/abajo/izquierda/derecha)
// que mira hacia el otro nodo, en vez del punto diagonal de interseccionConBorde,
// porque getBezierPath/getSmoothStepPath necesitan un Position de cada lado para
// orientar la curvatura/el codo recto.
function anclaCardinal(nodoBorde, nodoObjetivo) {
  const { width, height } = nodoBorde.measured
  const posBorde = nodoBorde.internals.positionAbsolute
  const posObjetivo = nodoObjetivo.internals.positionAbsolute

  const cx = posBorde.x + width / 2
  const cy = posBorde.y + height / 2
  const ox = posObjetivo.x + nodoObjetivo.measured.width / 2
  const oy = posObjetivo.y + nodoObjetivo.measured.height / 2
  const dx = ox - cx
  const dy = oy - cy

  let position
  if (Math.abs(dx) > Math.abs(dy)) {
    position = dx > 0 ? Position.Right : Position.Left
  } else {
    position = dy > 0 ? Position.Bottom : Position.Top
  }

  switch (position) {
    case Position.Right:
      return { x: posBorde.x + width, y: cy, position }
    case Position.Left:
      return { x: posBorde.x, y: cy, position }
    case Position.Bottom:
      return { x: cx, y: posBorde.y + height, position }
    default:
      return { x: cx, y: posBorde.y, position }
  }
}

function anguloSalida(position) {
  switch (position) {
    case Position.Right:
      return 0
    case Position.Bottom:
      return Math.PI / 2
    case Position.Left:
      return Math.PI
    default:
      return -Math.PI / 2
  }
}

function trianguloPuntos(tipX, tipY, angulo) {
  const baseX = tipX - LARGO_FORMA * Math.cos(angulo)
  const baseY = tipY - LARGO_FORMA * Math.sin(angulo)
  const dx = (ANCHO_FORMA / 2) * Math.sin(angulo)
  const dy = (ANCHO_FORMA / 2) * Math.cos(angulo)
  return `${tipX},${tipY} ${baseX + dx},${baseY - dy} ${baseX - dx},${baseY + dy}`
}

function romboPuntos(tipX, tipY, angulo) {
  const dirX = Math.cos(angulo)
  const dirY = Math.sin(angulo)
  const perpX = -Math.sin(angulo)
  const perpY = Math.cos(angulo)
  const medioX = tipX + (LARGO_FORMA / 2) * dirX
  const medioY = tipY + (LARGO_FORMA / 2) * dirY
  const finX = tipX + LARGO_FORMA * dirX
  const finY = tipY + LARGO_FORMA * dirY
  return [
    `${tipX},${tipY}`,
    `${medioX + (ANCHO_FORMA / 2) * perpX},${medioY + (ANCHO_FORMA / 2) * perpY}`,
    `${finX},${finY}`,
    `${medioX - (ANCHO_FORMA / 2) * perpX},${medioY - (ANCHO_FORMA / 2) * perpY}`,
  ].join(' ')
}

function flechaPuntos(tipX, tipY, angulo) {
  const baseX = tipX - LARGO_FLECHA * Math.cos(angulo)
  const baseY = tipY - LARGO_FLECHA * Math.sin(angulo)
  const dx = (ANCHO_FLECHA / 2) * Math.sin(angulo)
  const dy = (ANCHO_FLECHA / 2) * Math.cos(angulo)
  return `${baseX + dx},${baseY - dy} ${tipX},${tipY} ${baseX - dx},${baseY + dy}`
}

function RelacionEdge({ id, source, target, data, selected }) {
  const nodoOrigen = useInternalNode(source)
  const nodoDestino = useInternalNode(target)
  const { cambiarEstiloLinea } = usePizarra()

  if (!nodoOrigen || !nodoDestino) return null

  const { tipo, multiplicidadOrigen, multiplicidadDestino, nombre, estiloLinea = 'recta' } = data ?? {}

  let sourceX, sourceY, targetX, targetY, path, angulo, labelNombreX, labelNombreY

  if (estiloLinea === 'recta') {
    ;({ x: sourceX, y: sourceY } = interseccionConBorde(nodoOrigen, nodoDestino))
    ;({ x: targetX, y: targetY } = interseccionConBorde(nodoDestino, nodoOrigen))
    ;[path] = getStraightPath({ sourceX, sourceY, targetX, targetY })
    angulo = Math.atan2(targetY - sourceY, targetX - sourceX)
    labelNombreX = (sourceX + targetX) / 2
    labelNombreY = (sourceY + targetY) / 2
  } else {
    const anclaOrigen = anclaCardinal(nodoOrigen, nodoDestino)
    const anclaDestino = anclaCardinal(nodoDestino, nodoOrigen)
    sourceX = anclaOrigen.x
    sourceY = anclaOrigen.y
    targetX = anclaDestino.x
    targetY = anclaDestino.y
    angulo = anguloSalida(anclaOrigen.position)

    if (estiloLinea === 'curva') {
      const [p, lx, ly] = getBezierPath({
        sourceX,
        sourceY,
        sourcePosition: anclaOrigen.position,
        targetX,
        targetY,
        targetPosition: anclaDestino.position,
      })
      path = p
      labelNombreX = lx
      labelNombreY = ly
    } else {
      const [p, lx, ly] = getSmoothStepPath({
        sourceX,
        sourceY,
        sourcePosition: anclaOrigen.position,
        targetX,
        targetY,
        targetPosition: anclaDestino.position,
        borderRadius: 0,
      })
      path = p
      labelNombreX = lx
      labelNombreY = ly
    }
  }

  const trazoEstilo = {
    stroke: 'var(--text-muted)',
    strokeWidth: 1.5,
    strokeDasharray: tipo === 'dependencia' ? '6 4' : undefined,
  }

  const distancia = Math.hypot(targetX - sourceX, targetY - sourceY) || 1
  const unitX = Math.cos(angulo)
  const unitY = Math.sin(angulo)
  const OFFSET_MULTIPLICIDAD = Math.min(18, distancia / 2 - 6)
  const labelOrigen = {
    x: sourceX + unitX * OFFSET_MULTIPLICIDAD,
    y: sourceY + unitY * OFFSET_MULTIPLICIDAD,
  }
  const labelDestino = {
    x: targetX - unitX * OFFSET_MULTIPLICIDAD,
    y: targetY - unitY * OFFSET_MULTIPLICIDAD,
  }
  const labelNombre = {
    x: labelNombreX,
    y: labelNombreY,
  }

  return (
    <>
      <BaseEdge path={path} style={trazoEstilo} />

      {(tipo === 'asociacion' || tipo === 'dependencia') && (
        <polyline
          points={flechaPuntos(targetX, targetY, angulo)}
          fill="none"
          stroke="var(--text-muted)"
          strokeWidth={1.5}
        />
      )}

      {tipo === 'herencia' && (
        <polygon
          points={trianguloPuntos(targetX, targetY, angulo)}
          fill="var(--bg-panel)"
          stroke="var(--text-muted)"
          strokeWidth={1.5}
        />
      )}

      {tipo === 'agregacion' && (
        <polygon
          points={romboPuntos(sourceX, sourceY, angulo)}
          fill="var(--bg-panel)"
          stroke="var(--text-muted)"
          strokeWidth={1.5}
        />
      )}

      {tipo === 'composicion' && (
        <polygon
          points={romboPuntos(sourceX, sourceY, angulo)}
          fill="var(--text-muted)"
          stroke="var(--text-muted)"
          strokeWidth={1.5}
        />
      )}

      <EdgeLabelRenderer>
        {multiplicidadOrigen && (
          <div
            className={styles.etiqueta}
            style={{ transform: `translate(-50%, -50%) translate(${labelOrigen.x}px, ${labelOrigen.y}px)` }}
          >
            {multiplicidadOrigen}
          </div>
        )}
        {multiplicidadDestino && (
          <div
            className={styles.etiqueta}
            style={{ transform: `translate(-50%, -50%) translate(${labelDestino.x}px, ${labelDestino.y}px)` }}
          >
            {multiplicidadDestino}
          </div>
        )}
        {nombre && (
          <div
            className={styles.etiquetaNombre}
            style={{ transform: `translate(-50%, -50%) translate(${labelNombre.x}px, ${labelNombre.y}px)` }}
          >
            {nombre}
          </div>
        )}
        {selected && (
          <div
            className={`${styles.miniMenu} nopan nodrag`}
            style={{ transform: `translate(-50%, -50%) translate(${labelNombre.x}px, ${labelNombre.y - 26}px)` }}
          >
            {OPCIONES_ESTILO.map((opcion) => (
              <button
                key={opcion.valor}
                type="button"
                title={opcion.etiqueta}
                className={`${styles.miniMenuBoton} ${estiloLinea === opcion.valor ? styles.miniMenuBotonActivo : ''}`}
                onClick={(event) => {
                  event.stopPropagation()
                  cambiarEstiloLinea(id, opcion.valor)
                }}
              >
                <i className={`ti ${opcion.icono}`} />
              </button>
            ))}
          </div>
        )}
      </EdgeLabelRenderer>
    </>
  )
}

export default RelacionEdge
