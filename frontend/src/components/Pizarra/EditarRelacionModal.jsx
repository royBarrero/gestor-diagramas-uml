import { useState } from 'react'
import { createPortal } from 'react-dom'
import { TIPOS_RELACION } from '../../constants/tiposRelacion'
import { usePizarra } from '../../contexts/PizarraContext'
import styles from './MultiplicidadModal.module.css'

// Edita una relación ya existente (tipo, multiplicidad, nombre, clase de
// asociación) — se dispara desde el mini-menú de RelacionEdge.jsx cuando el
// edge está seleccionado.
function EditarRelacionModal({ relacion, onConfirmar, onCancelar }) {
  const { nodes, edges } = usePizarra()
  const datos = relacion.data ?? {}
  const [tipo, setTipo] = useState(datos.tipo ?? 'asociacion')
  const [origen, setOrigen] = useState(datos.multiplicidadOrigen ?? '')
  const [destino, setDestino] = useState(datos.multiplicidadDestino ?? '')
  const [nombre, setNombre] = useState(datos.nombre ?? '')
  const [claseAsociacion, setClaseAsociacion] = useState(() =>
    nodes.some((n) => n.id === datos.claseAsociacion) ? datos.claseAsociacion : ''
  )

  // Candidatas a clase de asociación: ni los extremos de esta relación ni una
  // clase que ya sea clase de asociación de otra relación (en UML cada clase de
  // asociación pertenece a una sola asociación).
  const usadasEnOtras = new Set(
    edges.filter((e) => e.id !== relacion.id && e.data?.claseAsociacion).map((e) => e.data.claseAsociacion)
  )
  const candidatas = nodes.filter(
    (n) => n.id !== relacion.source && n.id !== relacion.target && !usadasEnOtras.has(n.id)
  )

  function handleSubmit(event) {
    event.preventDefault()
    onConfirmar({
      tipo,
      multiplicidadOrigen: origen.trim() || null,
      multiplicidadDestino: destino.trim() || null,
      nombre: nombre.trim() || undefined,
      claseAsociacion: (tipo === 'asociacion' && claseAsociacion) || null,
    })
  }

  return createPortal(
    <div className={styles.overlay} onClick={onCancelar}>
      <div className={styles.modal} onClick={(event) => event.stopPropagation()}>
        <h2 className={styles.titulo}>Editar relación</h2>
        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.label} htmlFor="rel-tipo">
            Tipo de relación
          </label>
          <select
            id="rel-tipo"
            className={styles.input}
            value={tipo}
            onChange={(event) => setTipo(event.target.value)}
          >
            {TIPOS_RELACION.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.etiqueta}
              </option>
            ))}
          </select>

          <label className={styles.label} htmlFor="edit-mult-origen">
            Extremo origen (ej: 1, 0..1, 0..*, 1..*)
          </label>
          <input
            id="edit-mult-origen"
            className={styles.input}
            value={origen}
            onChange={(event) => setOrigen(event.target.value)}
            autoFocus
          />

          <label className={styles.label} htmlFor="edit-mult-destino">
            Extremo destino
          </label>
          <input
            id="edit-mult-destino"
            className={styles.input}
            value={destino}
            onChange={(event) => setDestino(event.target.value)}
          />

          <label className={styles.label} htmlFor="edit-rel-nombre">
            Nombre de la relación (opcional)
          </label>
          <input
            id="edit-rel-nombre"
            className={styles.input}
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
          />

          {tipo === 'asociacion' && (
            <>
              <label className={styles.label} htmlFor="edit-rel-clase-asociacion">
                Clase de asociación (opcional)
              </label>
              <select
                id="edit-rel-clase-asociacion"
                className={styles.input}
                value={claseAsociacion}
                onChange={(event) => setClaseAsociacion(event.target.value)}
              >
                <option value="">Ninguna</option>
                {candidatas.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.data.nombre}
                  </option>
                ))}
              </select>
            </>
          )}

          <div className={styles.acciones}>
            <button type="button" className={styles.botonCancelar} onClick={onCancelar}>
              Cancelar
            </button>
            <button type="submit" className={styles.botonGuardar}>
              Guardar
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}

export default EditarRelacionModal
