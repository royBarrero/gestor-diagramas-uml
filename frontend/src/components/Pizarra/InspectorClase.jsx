import { useState } from 'react'
import { usePizarra } from '../../contexts/PizarraContext'
import { TIPOS_DATO } from '../../constants/tiposDato'
import { TIPOS_CLASE } from '../../constants/tiposClase'
import styles from './InspectorClase.module.css'

const SIMBOLOS = { publico: '+', privado: '-', protegido: '#', paquete: '~' }
const ORDEN_VISIBILIDAD = ['publico', 'protegido', 'paquete', 'privado']
const OPCION_OTRO = '__otro'

function cicloVisibilidad(actual) {
  const indice = ORDEN_VISIBILIDAD.indexOf(actual)
  return ORDEN_VISIBILIDAD[(indice + 1) % ORDEN_VISIBILIDAD.length]
}

function InspectorClase() {
  const {
    claseSeleccionada: clase,
    seleccionarClase,
    renombrarClase,
    cambiarTipoClase,
    editarCampoItem,
    pedirEliminarClase,
  } = usePizarra()
  // Atributos para los que el usuario eligió "Otro…" y escribe el tipo a mano.
  const [tipoLibre, setTipoLibre] = useState(() => new Set())

  if (!clase) return null

  const atributos = clase.data.atributos ?? []
  const metodos = clase.data.metodos ?? []
  const esEnumeracion = clase.data.tipoClase === 'enumeracion'

  function marcarTipoLibre(itemId, activo) {
    setTipoLibre((actual) => {
      const nuevo = new Set(actual)
      if (activo) nuevo.add(itemId)
      else nuevo.delete(itemId)
      return nuevo
    })
  }

  function handleSelectTipo(item, valor) {
    if (valor === OPCION_OTRO) {
      marcarTipoLibre(item.id, true)
      editarCampoItem(clase.id, 'atributos', item.id, { tipo: '' })
    } else {
      editarCampoItem(clase.id, 'atributos', item.id, { tipo: valor })
    }
  }

  function volverALista(item) {
    marcarTipoLibre(item.id, false)
    if (!TIPOS_DATO.includes(item.tipo)) editarCampoItem(clase.id, 'atributos', item.id, { tipo: '' })
  }

  // UML: un miembro estático (de clase, no de instancia) se muestra subrayado.
  function renderEstatico(campo, item) {
    return (
      <button
        type="button"
        className={`${styles.estatico} ${item.estatico ? styles.estaticoActivo : ''}`}
        onClick={() => editarCampoItem(clase.id, campo, item.id, { estatico: !item.estatico })}
        title={item.estatico ? 'Estático (clic para hacerlo de instancia)' : 'De instancia (clic para hacerlo estático)'}
        aria-pressed={Boolean(item.estatico)}
      >
        S
      </button>
    )
  }

  function renderVisibilidad(campo, item) {
    return (
      <button
        type="button"
        className={styles.visibilidad}
        onClick={() => editarCampoItem(clase.id, campo, item.id, { visibilidad: cicloVisibilidad(item.visibilidad) })}
        title="Cambiar visibilidad"
      >
        {SIMBOLOS[item.visibilidad]}
      </button>
    )
  }

  return (
    <aside className={styles.panel} aria-label="Editar clase">
      <div className={styles.header}>
        <span className={styles.punto} />
        <span className={styles.titulo}>{clase.data.nombre}</span>
        <span className={styles.editando}>Editando</span>
        <button type="button" className={styles.botonCerrar} onClick={() => seleccionarClase(null)} title="Cerrar">
          <i className="ti ti-x" />
        </button>
      </div>

      <label className={styles.campoNombre}>
        Nombre
        <input value={clase.data.nombre} onChange={(event) => renombrarClase(clase.id, event.target.value)} />
      </label>

      <label className={styles.campoNombre}>
        Tipo de clase
        <select
          value={clase.data.tipoClase ?? 'clase'}
          onChange={(event) => cambiarTipoClase(clase.id, event.target.value)}
        >
          {TIPOS_CLASE.map((tipo) => (
            <option key={tipo.valor} value={tipo.valor}>
              {tipo.etiqueta}
            </option>
          ))}
        </select>
      </label>

      {esEnumeracion ? (
        <section className={styles.seccion}>
          <h3 className={styles.subtitulo}>Literales</h3>
          {atributos.map((item) => (
            <div key={item.id} className={styles.fila}>
              <span className={styles.nombreItem}>{item.texto || '(sin nombre)'}</span>
            </div>
          ))}
          {atributos.length === 0 && (
            <p className={styles.vacio}>Todavía no tiene literales. Escribilos directo en la caja, en “+ literal”.</p>
          )}
        </section>
      ) : (
        <section className={styles.seccion}>
          <div className={styles.seccionHeader}>
            <h3 className={styles.subtitulo}>Atributos</h3>
            <span className={styles.subtituloSecundario}>Tipo</span>
          </div>
          {atributos.map((item) => {
            const libre = tipoLibre.has(item.id) || (item.tipo && !TIPOS_DATO.includes(item.tipo))
            return (
              <div key={item.id} className={styles.fila}>
                {renderVisibilidad('atributos', item)}
                {renderEstatico('atributos', item)}
                <span className={styles.nombreItem}>{item.texto || '(sin nombre)'}</span>
                {libre ? (
                  <>
                    <input
                      className={`${styles.control} ${styles.tipoLibre}`}
                      placeholder="Tipo"
                      value={item.tipo ?? ''}
                      onChange={(event) => editarCampoItem(clase.id, 'atributos', item.id, { tipo: event.target.value })}
                      autoFocus={tipoLibre.has(item.id) && !item.tipo}
                    />
                    <button
                      type="button"
                      className={styles.botonLista}
                      onClick={() => volverALista(item)}
                      title="Volver a la lista de tipos"
                    >
                      <i className="ti ti-list" />
                    </button>
                  </>
                ) : (
                  <select
                    className={`${styles.control} ${styles.selectTipo}`}
                    value={item.tipo ?? ''}
                    onChange={(event) => handleSelectTipo(item, event.target.value)}
                  >
                    <option value="">Elegí…</option>
                    {TIPOS_DATO.map((tipo) => (
                      <option key={tipo} value={tipo}>
                        {tipo}
                      </option>
                    ))}
                    <option value={OPCION_OTRO}>Otro… (escribir)</option>
                  </select>
                )}
              </div>
            )
          })}
          {atributos.length === 0 && (
            <p className={styles.vacio}>Todavía no tiene atributos. Escribilos directo en la caja de la clase, en “+ atributo”.</p>
          )}
        </section>
      )}

      <section className={styles.seccion}>
        <h3 className={styles.subtitulo}>Métodos</h3>
        {metodos.map((item) => (
          <div key={item.id} className={styles.fila}>
            {renderVisibilidad('metodos', item)}
            {renderEstatico('metodos', item)}
            <span className={styles.nombreItem}>{item.texto || '(sin nombre)'}</span>
          </div>
        ))}
        {metodos.length === 0 && <p className={styles.vacio}>Sin métodos.</p>}
      </section>

      <p className={styles.nota}>Los atributos y métodos se agregan, editan y ordenan desde la caja de la clase.</p>

      <button type="button" className={styles.botonEliminar} onClick={() => pedirEliminarClase(clase.id)}>
        Eliminar clase
      </button>
    </aside>
  )
}

export default InspectorClase
