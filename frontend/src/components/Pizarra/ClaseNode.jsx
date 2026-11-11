import { useRef, useState } from 'react'
import { Handle, Position } from '@xyflow/react'
import { usePizarra } from '../../contexts/PizarraContext'
import { infoTipoClase } from '../../constants/tiposClase'
import styles from './ClaseNode.module.css'

const SIMBOLOS = { publico: '+', privado: '-', protegido: '#', paquete: '~' }

// `esLiteral`: fila de una enumeración — UML muestra solo el nombre del literal,
// sin visibilidad ni tipo.
function FilaCampo({ item, esLiteral, esPrimero, esUltimo, onRenombrar, onMover, onEliminar }) {
  const [editando, setEditando] = useState(false)
  // Esc dispara un blur al cerrar el input; esta marca evita que ese blur confirme.
  const cancelado = useRef(false)

  function handleBlur(event) {
    const valor = event.target.value.trim()
    if (!cancelado.current && valor && valor !== item.texto) onRenombrar(valor)
    cancelado.current = false
    setEditando(false)
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter') {
      event.target.blur()
    } else if (event.key === 'Escape') {
      cancelado.current = true
      event.target.blur()
    } else if (event.altKey && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
      event.preventDefault()
      onMover(event.key === 'ArrowUp' ? -1 : 1)
    }
  }

  if (editando) {
    return (
      <input
        className={`${styles.input} nodrag`}
        defaultValue={item.texto}
        autoFocus
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
      />
    )
  }

  return (
    <div className={styles.fila}>
      <button
        type="button"
        className={`${styles.textoFila} nodrag`}
        onClick={() => setEditando(true)}
        title="Clic para editar"
      >
        {!esLiteral && <span className={styles.simbolo}>{SIMBOLOS[item.visibilidad]}</span>}
        <span className={`${styles.nombreItem} ${item.estatico ? styles.estatico : ''}`}>{item.texto || ' '}</span>
      </button>
      {!esLiteral && item.tipo && (
        <span className={styles.tipo}>
          : <span className={styles.tipoValor}>{item.tipo}</span>
        </span>
      )}
      <div className={`${styles.acciones} nodrag`}>
        <button type="button" onClick={() => onMover(-1)} disabled={esPrimero} title="Subir">
          <i className="ti ti-chevron-up" />
        </button>
        <button type="button" onClick={() => onMover(1)} disabled={esUltimo} title="Bajar">
          <i className="ti ti-chevron-down" />
        </button>
        <button type="button" onClick={onEliminar} title="Eliminar">
          <i className="ti ti-x" />
        </button>
      </div>
    </div>
  )
}

function SeccionCampos({ claseId, campo, items, esLiteral = false }) {
  const { agregarCampoItem, editarCampoItem, moverCampoItem, eliminarCampoItem } = usePizarra()
  const [escribiendo, setEscribiendo] = useState(false)
  const cancelado = useRef(false)
  const etiqueta = esLiteral ? 'literal' : campo === 'atributos' ? 'atributo' : 'método'

  // Enter agrega el ítem y deja el campo vacío para el siguiente; Enter sin
  // texto, Esc o salir del campo cierran el borrador.
  function handleKeyDown(event) {
    if (event.key === 'Enter') {
      event.preventDefault()
      const valor = event.target.value.trim()
      if (!valor) {
        cancelado.current = true
        event.target.blur()
        return
      }
      agregarCampoItem(claseId, campo, { texto: valor })
      event.target.value = ''
    } else if (event.key === 'Escape') {
      cancelado.current = true
      event.target.blur()
    }
  }

  function handleBlur(event) {
    const valor = event.target.value.trim()
    if (!cancelado.current && valor) agregarCampoItem(claseId, campo, { texto: valor })
    cancelado.current = false
    setEscribiendo(false)
  }

  return (
    <div className={styles.seccion}>
      {items.map((item, indice) => (
        <FilaCampo
          key={item.id}
          item={item}
          esLiteral={esLiteral}
          esPrimero={indice === 0}
          esUltimo={indice === items.length - 1}
          onRenombrar={(texto) => editarCampoItem(claseId, campo, item.id, { texto })}
          onMover={(direccion) => moverCampoItem(claseId, campo, item.id, direccion)}
          onEliminar={() => eliminarCampoItem(claseId, campo, item.id)}
        />
      ))}
      {escribiendo ? (
        <input
          className={`${styles.input} nodrag`}
          placeholder={`nombre del ${etiqueta}`}
          autoFocus
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
        />
      ) : (
        <button type="button" className={`${styles.botonAgregar} nodrag`} onClick={() => setEscribiendo(true)}>
          + {etiqueta}
        </button>
      )}
    </div>
  )
}

function ClaseNode({ id, data }) {
  const { renombrarClase, origenConexionId, seleccionId } = usePizarra()
  const [editandoNombre, setEditandoNombre] = useState(false)
  const esOrigenConexion = origenConexionId === id
  const seleccionada = seleccionId === id

  function commitNombre(event) {
    const valor = event.target.value.trim()
    renombrarClase(id, valor || data.nombre)
    setEditandoNombre(false)
  }

  const clasesContenido = [
    styles.contenido,
    seleccionada ? styles.seleccionada : '',
    esOrigenConexion ? styles.origen : '',
  ].join(' ')

  const presencias = data.presencias ?? []
  const otraPersona = presencias.find((p) => !p.esYo)
  const sugerencia = data.sugerencia
  const tipoClase = infoTipoClase(data.tipoClase)

  // El botón está dentro del nodo: sin esto, el clic también seleccionaría la clase.
  function handleClickSugerencia(event) {
    event.stopPropagation()
    sugerencia.onAbrir()
  }

  return (
    <div className={styles.nodo}>
      {presencias.length > 0 && (
        <div className={styles.tagsPresencia} data-no-exportar="true">
          {presencias.map((p) => (
            <div key={p.id} className={styles.tagPresencia} style={{ color: p.color, borderColor: p.color }}>
              <span className={styles.punto} style={{ background: p.color }} />
              {p.esYo ? 'Vos' : `${p.nombre} editando`}
            </div>
          ))}
        </div>
      )}

      {sugerencia?.esParaMi && <div className={styles.marcoAlerta} data-no-exportar="true" />}
      {data.resaltada && <div key={data.resaltada} className={styles.marcoResaltado} data-no-exportar="true" />}

      <Handle id="top" type="source" position={Position.Top} className={styles.handle} />
      <Handle id="right" type="source" position={Position.Right} className={styles.handle} />
      <Handle id="bottom" type="source" position={Position.Bottom} className={styles.handle} />
      <Handle id="left" type="source" position={Position.Left} className={styles.handle} />

      <div
        className={clasesContenido}
        style={otraPersona && !seleccionada ? { borderColor: otraPersona.color } : undefined}
      >
        <div className={styles.header} onDoubleClick={() => setEditandoNombre(true)}>
          <span className={styles.punto} style={otraPersona ? { background: otraPersona.color } : undefined} />
          {tipoClase.palabraClave && !editandoNombre && (
            <span className={styles.palabraClave}>{tipoClase.palabraClave}</span>
          )}
          {editandoNombre ? (
            <input
              className={`${styles.inputNombre} nodrag`}
              defaultValue={data.nombre}
              autoFocus
              onBlur={commitNombre}
              onKeyDown={(event) => event.key === 'Enter' && event.target.blur()}
            />
          ) : (
            <span className={`${styles.nombre} ${data.tipoClase === 'abstracta' ? styles.nombreAbstracto : ''}`}>
              {data.nombre}
            </span>
          )}
          {sugerencia?.esParaMi && (
            <button
              type="button"
              className={`${styles.botonAlerta} nodrag`}
              data-no-exportar="true"
              onClick={handleClickSugerencia}
              onDoubleClick={(event) => event.stopPropagation()}
              title="Ver la sugerencia de la IA"
              aria-label="Ver la sugerencia de la IA"
            >
              <i className="ti ti-alert-triangle" />
            </button>
          )}
          {sugerencia && !sugerencia.esParaMi && (
            <button
              type="button"
              className={`${styles.botonSugerenciaAjena} nodrag`}
              data-no-exportar="true"
              onClick={handleClickSugerencia}
              onDoubleClick={(event) => event.stopPropagation()}
              title={`Sugerencia de la IA para ${sugerencia.destinoNombre}`}
              aria-label={`Sugerencia de la IA para ${sugerencia.destinoNombre}`}
            >
              <i className="ti ti-sparkles" />
              {sugerencia.destinoNombre?.[0]?.toUpperCase() ?? '?'}
            </button>
          )}
          {tipoClase.propiedad && <span className={styles.estereotipo}>{tipoClase.propiedad}</span>}
        </div>

        <SeccionCampos
          claseId={id}
          campo="atributos"
          items={data.atributos ?? []}
          esLiteral={data.tipoClase === 'enumeracion'}
        />
        <div className={styles.separador} />
        <SeccionCampos claseId={id} campo="metodos" items={data.metodos ?? []} />
      </div>
    </div>
  )
}

export default ClaseNode
