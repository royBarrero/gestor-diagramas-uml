import { useEffect, useRef, useState } from 'react'
import { useReactFlow } from '@xyflow/react'
import { usePizarra } from '../../contexts/PizarraContext'
import { TIPOS_DATO } from '../../constants/tiposDato'
import styles from './PanelClases.module.css'

const SIMBOLOS = { publico: '+', privado: '-', protegido: '#' }
const ORDEN_VISIBILIDAD = ['publico', 'protegido', 'privado']

function cicloVisibilidad(actual) {
  const indice = ORDEN_VISIBILIDAD.indexOf(actual)
  return ORDEN_VISIBILIDAD[(indice + 1) % ORDEN_VISIBILIDAD.length]
}

function PanelClases() {
  const {
    nodes,
    seleccionId,
    seleccionarClase,
    agregarClase,
    panelClasesAbierto,
    alternarPanelClases,
    renombrarClase,
    agregarCampoItem,
    editarCampoItem,
    eliminarCampoItem,
    moverCampoItem,
    pedirEliminarClase,
  } = usePizarra()
  const { setCenter } = useReactFlow()
  const inputRefs = useRef(new Map())
  const [idAEnfocar, setIdAEnfocar] = useState(null)

  useEffect(() => {
    if (idAEnfocar && inputRefs.current.has(idAEnfocar)) {
      inputRefs.current.get(idAEnfocar).focus()
      setIdAEnfocar(null)
    }
  }, [idAEnfocar])

  function handleClick(nodo) {
    seleccionarClase(seleccionId === nodo.id ? null : nodo.id)
    setCenter(nodo.position.x + 90, nodo.position.y + 60, { zoom: 1, duration: 400 })
  }

  function handleEnter(claseId, campo, esUltimo, event) {
    if (event.key === 'Enter' && esUltimo) {
      event.preventDefault()
      const nuevoId = agregarCampoItem(claseId, campo)
      setIdAEnfocar(nuevoId)
    }
  }

  function renderLista(claseId, campo, items) {
    return (
      <div className={styles.seccion}>
        <h3 className={styles.subtitulo}>{campo === 'atributos' ? 'Atributos' : 'Métodos'}</h3>
        {campo === 'atributos' && (
          <datalist id="tipos-dato">
            {TIPOS_DATO.map((tipo) => (
              <option key={tipo} value={tipo} />
            ))}
          </datalist>
        )}
        {items.map((item, indice) => (
          <div key={item.id} className={styles.fila}>
            <button
              type="button"
              className={styles.simbolo}
              onClick={() =>
                editarCampoItem(claseId, campo, item.id, { visibilidad: cicloVisibilidad(item.visibilidad) })
              }
              title="Cambiar visibilidad"
            >
              {SIMBOLOS[item.visibilidad]}
            </button>
            {campo === 'atributos' && (
              <input
                className={styles.inputTipo}
                list="tipos-dato"
                placeholder="Tipo"
                value={item.tipo ?? ''}
                onChange={(event) => editarCampoItem(claseId, campo, item.id, { tipo: event.target.value })}
              />
            )}
            <input
              ref={(el) => {
                if (el) inputRefs.current.set(item.id, el)
                else inputRefs.current.delete(item.id)
              }}
              className={styles.inputFila}
              placeholder="Nombre"
              value={item.texto}
              onChange={(event) => editarCampoItem(claseId, campo, item.id, { texto: event.target.value })}
              onKeyDown={(event) => handleEnter(claseId, campo, indice === items.length - 1, event)}
            />
            <div className={styles.flechas}>
              <button
                type="button"
                className={styles.botonFlecha}
                disabled={indice === 0}
                onClick={() => moverCampoItem(claseId, campo, item.id, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                className={styles.botonFlecha}
                disabled={indice === items.length - 1}
                onClick={() => moverCampoItem(claseId, campo, item.id, 1)}
              >
                ↓
              </button>
            </div>
            <button
              type="button"
              className={styles.botonEliminarFila}
              onClick={() => eliminarCampoItem(claseId, campo, item.id)}
              title="Eliminar"
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          className={styles.botonAgregarFila}
          onClick={() => agregarCampoItem(claseId, campo)}
        >
          + {campo === 'atributos' ? 'atributo' : 'método'}
        </button>
      </div>
    )
  }

  if (!panelClasesAbierto) {
    return (
      <div className={styles.franja}>
        <button
          type="button"
          className={styles.botonFranja}
          onClick={alternarPanelClases}
          title="Mostrar panel de clases"
        >
          <i className="ti ti-layout-sidebar-left-expand" />
        </button>
      </div>
    )
  }

  return (
    <aside className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.titulo}>Clases</h2>
        <div className={styles.headerAcciones}>
          <button type="button" className={styles.botonIcono} onClick={agregarClase} title="Nueva clase">
            <i className="ti ti-plus" />
          </button>
          <button
            type="button"
            className={styles.botonIcono}
            onClick={alternarPanelClases}
            title="Ocultar panel"
          >
            <i className="ti ti-layout-sidebar-left-collapse" />
          </button>
        </div>
      </div>
      <ul className={styles.lista}>
        {nodes.map((nodo) => {
          const seleccionada = seleccionId === nodo.id
          return (
            <li key={nodo.id} className={styles.item}>
              <button
                type="button"
                className={`${styles.itemBoton} ${seleccionada ? styles.itemActivo : ''}`}
                onClick={() => handleClick(nodo)}
              >
                {nodo.data.nombre}
              </button>

              {seleccionada && (
                <div className={styles.editor}>
                  <label className={styles.label} htmlFor={`nombre-${nodo.id}`}>
                    Nombre
                  </label>
                  <input
                    id={`nombre-${nodo.id}`}
                    className={styles.inputNombre}
                    value={nodo.data.nombre}
                    onChange={(event) => renombrarClase(nodo.id, event.target.value)}
                  />

                  {renderLista(nodo.id, 'atributos', nodo.data.atributos ?? [])}
                  {renderLista(nodo.id, 'metodos', nodo.data.metodos ?? [])}

                  <button
                    type="button"
                    className={styles.botonEliminarClase}
                    onClick={() => pedirEliminarClase(nodo.id)}
                  >
                    Eliminar clase
                  </button>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </aside>
  )
}

export default PanelClases
