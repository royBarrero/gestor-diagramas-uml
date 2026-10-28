import { useState } from 'react'
import { useReactFlow } from '@xyflow/react'
import { usePizarra } from '../../contexts/PizarraContext'
import styles from './ListaClases.module.css'

// Recibe los nodos ya combinados con la presencia de los colaboradores (los
// arma Pizarra), para mostrar quién está editando cada clase.
function ListaClases({ nodos }) {
  const { seleccionarClase, cerrarListaClases } = usePizarra()
  const { setCenter } = useReactFlow()
  const [busqueda, setBusqueda] = useState('')

  const filtro = busqueda.trim().toLowerCase()
  const visibles = filtro ? nodos.filter((n) => n.data.nombre.toLowerCase().includes(filtro)) : nodos

  function handleClick(nodo) {
    seleccionarClase(nodo.id)
    setCenter(nodo.position.x + 120, nodo.position.y + 80, { zoom: 1, duration: 400 })
    cerrarListaClases()
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.titulo}>Clases ({nodos.length})</span>
        <button type="button" className={styles.botonCerrar} onClick={cerrarListaClases} title="Cerrar lista">
          <i className="ti ti-x" />
        </button>
      </div>

      <label className={styles.buscador}>
        <i className="ti ti-search" />
        <input
          placeholder="Buscar clase"
          value={busqueda}
          onChange={(event) => setBusqueda(event.target.value)}
          autoFocus
        />
      </label>

      <ul className={styles.lista}>
        {visibles.map((nodo) => (
          <li key={nodo.id}>
            <button type="button" className={styles.item} onClick={() => handleClick(nodo)}>
              <span
                className={styles.punto}
                style={nodo.data.presencia ? { background: nodo.data.presencia.color } : undefined}
              />
              <span className={styles.nombre}>{nodo.data.nombre}</span>
              {nodo.data.presencia && <span className={styles.quien}>{nodo.data.presencia.nombre}</span>}
            </button>
          </li>
        ))}
        {visibles.length === 0 && (
          <li className={styles.vacio}>{nodos.length === 0 ? 'Todavía no hay clases.' : 'Ninguna clase coincide.'}</li>
        )}
      </ul>
    </div>
  )
}

export default ListaClases
