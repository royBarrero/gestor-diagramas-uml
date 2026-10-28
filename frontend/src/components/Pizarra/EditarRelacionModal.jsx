import { useState } from 'react'
import { TIPOS_RELACION } from '../../constants/tiposRelacion'
import { usePizarra } from '../../contexts/PizarraContext'
import ModalPizarra from './ModalPizarra'
import { CampoMultiplicidad } from './MultiplicidadModal'
import styles from './ModalPizarra.module.css'

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

  const nombreOrigen = nodes.find((n) => n.id === relacion.source)?.data.nombre
  const nombreDestino = nodes.find((n) => n.id === relacion.target)?.data.nombre

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

  return (
    <ModalPizarra
      titulo="Editar relación"
      subtitulo={nombreOrigen && nombreDestino ? `${nombreOrigen} → ${nombreDestino}` : undefined}
      icono="ti-pencil"
      onCerrar={onCancelar}
    >
      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.campo}>
          <label className={styles.label} htmlFor="rel-tipo">
            Tipo de relación
          </label>
          <select id="rel-tipo" className={styles.input} value={tipo} onChange={(event) => setTipo(event.target.value)}>
            {TIPOS_RELACION.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.etiqueta}
              </option>
            ))}
          </select>
        </div>

        <CampoMultiplicidad
          id="edit-mult-origen"
          etiqueta={`Multiplicidad en ${nombreOrigen ?? 'el origen'}`}
          valor={origen}
          onCambiar={setOrigen}
          autoFocus
        />
        <CampoMultiplicidad
          id="edit-mult-destino"
          etiqueta={`Multiplicidad en ${nombreDestino ?? 'el destino'}`}
          valor={destino}
          onCambiar={setDestino}
        />

        <div className={styles.campo}>
          <label className={styles.label} htmlFor="edit-rel-nombre">
            Nombre de la relación <span className={styles.opcional}>(opcional)</span>
          </label>
          <input
            id="edit-rel-nombre"
            className={styles.input}
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
          />
        </div>

        {tipo === 'asociacion' && (
          <div className={styles.campo}>
            <label className={styles.label} htmlFor="edit-rel-clase-asociacion">
              Clase de asociación <span className={styles.opcional}>(opcional)</span>
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
          </div>
        )}

        <div className={styles.acciones}>
          <button type="button" className={styles.botonCancelar} onClick={onCancelar}>
            Cancelar
          </button>
          <button type="submit" className={styles.botonPrimario}>
            Guardar
          </button>
        </div>
      </form>
    </ModalPizarra>
  )
}

export default EditarRelacionModal
