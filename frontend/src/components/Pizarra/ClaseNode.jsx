import { useState } from 'react'
import { Handle, Position } from '@xyflow/react'
import { usePizarra } from '../../contexts/PizarraContext'
import styles from './ClaseNode.module.css'

const SIMBOLOS = { publico: '+', privado: '-', protegido: '#' }

function FilaCampo({ item, editando, onDoubleClick, onCommit }) {
  return (
    <div className={styles.fila} onDoubleClick={onDoubleClick}>
      <span className={styles.simbolo}>{SIMBOLOS[item.visibilidad]}</span>
      {editando ? (
        <input
          className={`${styles.inputFila} nodrag`}
          defaultValue={item.texto}
          autoFocus
          onBlur={onCommit}
          onKeyDown={(event) => event.key === 'Enter' && event.target.blur()}
        />
      ) : (
        <span className={styles.texto}>{(item.tipo ? `${item.texto}: ${item.tipo}` : item.texto) || ' '}</span>
      )}
    </div>
  )
}

function ClaseNode({ id, data }) {
  const { renombrarClase, editarCampoItem, pedirEliminarClase, origenConexionId } = usePizarra()
  const [editandoNombre, setEditandoNombre] = useState(false)
  const [itemEditando, setItemEditando] = useState(null)
  const esOrigenConexion = origenConexionId === id

  function commitNombre(event) {
    const valor = event.target.value.trim()
    renombrarClase(id, valor || data.nombre)
    setEditandoNombre(false)
  }

  function commitItem(campo, itemId, event) {
    editarCampoItem(id, campo, itemId, { texto: event.target.value })
    setItemEditando(null)
  }

  return (
    <div className={styles.nodo}>
      {data.presencia && (
        <div className={styles.tagPresencia} style={{ background: data.presencia.color }}>
          <i className="ti ti-pointer" /> {data.presencia.nombre}
        </div>
      )}

      <Handle id="top" type="source" position={Position.Top} className={styles.handle} />
      <Handle id="right" type="source" position={Position.Right} className={styles.handle} />
      <Handle id="bottom" type="source" position={Position.Bottom} className={styles.handle} />
      <Handle id="left" type="source" position={Position.Left} className={styles.handle} />

      <div
        className={`${styles.contenido} ${esOrigenConexion ? styles.origen : ''}`}
        style={data.presencia ? { borderColor: data.presencia.color } : undefined}
      >
        <div className={styles.header} onDoubleClick={() => setEditandoNombre(true)}>
          {editandoNombre ? (
            <input
              className={`${styles.inputNombre} nodrag`}
              defaultValue={data.nombre}
              autoFocus
              onBlur={commitNombre}
              onKeyDown={(event) => event.key === 'Enter' && event.target.blur()}
            />
          ) : (
            <span className={styles.nombre}>{data.nombre}</span>
          )}
          <button
            type="button"
            className={`${styles.botonEliminar} nodrag`}
            onClick={() => pedirEliminarClase(id)}
            title="Eliminar clase"
          >
            ×
          </button>
        </div>

        <div className={styles.seccion}>
          {(data.atributos ?? []).map((atributo) => (
            <FilaCampo
              key={atributo.id}
              item={atributo}
              editando={itemEditando?.campo === 'atributos' && itemEditando.itemId === atributo.id}
              onDoubleClick={() => setItemEditando({ campo: 'atributos', itemId: atributo.id })}
              onCommit={(event) => commitItem('atributos', atributo.id, event)}
            />
          ))}
        </div>

        <div className={styles.separador} />

        <div className={styles.seccion}>
          {(data.metodos ?? []).map((metodo) => (
            <FilaCampo
              key={metodo.id}
              item={metodo}
              editando={itemEditando?.campo === 'metodos' && itemEditando.itemId === metodo.id}
              onDoubleClick={() => setItemEditando({ campo: 'metodos', itemId: metodo.id })}
              onCommit={(event) => commitItem('metodos', metodo.id, event)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

export default ClaseNode
