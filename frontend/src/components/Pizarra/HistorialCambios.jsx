import { useEffect, useState } from 'react'
import { fechaRelativa } from '../../utils/fechaRelativa'
import styles from './HistorialCambios.module.css'

const MS_REFRESCO_HORA = 60000

function Entrada({ entrada, existe, avisar, onTocar }) {
  const contenido = (
    <>
      {entrada.por_agente ? (
        <span className={styles.avatarAgente} aria-hidden="true">
          <i className="ti ti-sparkles" />
        </span>
      ) : (
        <span className={styles.avatar} style={{ background: entrada.autor_color }} aria-hidden="true">
          {entrada.autor_nombre?.[0]?.toUpperCase() ?? '?'}
        </span>
      )}
      <span className={styles.cuerpo}>
        <span className={styles.texto}>
          <b className={entrada.por_agente ? styles.nombreAgente : undefined}>
            {entrada.por_agente ? 'Agente IA' : entrada.autor_nombre}
          </b>{' '}
          {entrada.resumen}
        </span>
        {entrada.por_agente && <span className={styles.leyenda}>a pedido de {entrada.autor_nombre}</span>}
        <span className={styles.meta}>
          {entrada.nombre_elemento && (
            <span className={existe ? styles.clase : styles.claseEliminada}>{entrada.nombre_elemento}</span>
          )}
          <span>{fechaRelativa(entrada.created_at)}</span>
        </span>
        {avisar && (
          <span className={styles.avisoEliminada} role="status">
            <i className="ti ti-info-circle" aria-hidden="true" /> Esta clase ya no existe
          </span>
        )}
      </span>
    </>
  )

  // Foto e importación no son sobre una clase: no hay adónde ir.
  if (!entrada.id_elemento) return <div className={styles.entrada}>{contenido}</div>
  return (
    <button type="button" className={`${styles.entrada} ${styles.entradaTocable}`} onClick={onTocar}>
      {contenido}
    </button>
  )
}

// CU18: quién cambió qué y cuándo, en la pestaña Historial del panel derecho.
function HistorialCambios({ historial, nodos, visible, onIrAClase }) {
  const { entradas, filtros, opciones, cargando, hayAnteriores, errorCarga } = historial
  const [avisoId, setAvisoId] = useState(null)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [, setRefresco] = useState(0)

  // Para que "Hace 5 min" no quede congelado mientras se mira la lista.
  useEffect(() => {
    if (!visible) return undefined
    const intervalo = setInterval(() => setRefresco((n) => n + 1), MS_REFRESCO_HORA)
    return () => clearInterval(intervalo)
  }, [visible])

  const idsVigentes = new Set(nodos.map((n) => n.id))

  // Las del lienzo, con su nombre de ahora, más las que solo quedan en el historial.
  const clases = [
    ...nodos.map((n) => ({ id: n.id, nombre: n.data.nombre })),
    ...opciones.clases.filter((c) => !idsVigentes.has(c.id)).map((c) => ({ ...c, nombre: `${c.nombre} (eliminada)` })),
  ].sort((a, b) => a.nombre.localeCompare(b.nombre))

  function handleTocar(entrada) {
    if (idsVigentes.has(entrada.id_elemento)) {
      setAvisoId(null)
      onIrAClase(entrada.id_elemento)
    } else {
      setAvisoId(entrada.id)
    }
  }

  async function handleCargarAnteriores() {
    setCargandoMas(true)
    await historial.cargarAnteriores()
    setCargandoMas(false)
  }

  const hayFiltros = Boolean(filtros.usuarioId || filtros.claseId)

  return (
    <div className={styles.historial}>
      <div className={styles.filtros}>
        <select
          className={styles.filtro}
          aria-label="Filtrar por integrante"
          value={filtros.usuarioId}
          onChange={(event) => historial.cambiarFiltros({ usuarioId: event.target.value })}
        >
          <option value="">Todos los integrantes</option>
          {opciones.integrantes.map((i) => (
            <option key={i.id} value={i.id}>
              {i.nombre}
            </option>
          ))}
        </select>
        <select
          className={styles.filtro}
          aria-label="Filtrar por clase"
          value={filtros.claseId}
          onChange={(event) => historial.cambiarFiltros({ claseId: event.target.value })}
        >
          <option value="">Todas las clases</option>
          {clases.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.lista} aria-live="polite">
        {errorCarga && (
          <div className={styles.errorCarga}>
            No se pudo cargar el historial.
            <button type="button" className={styles.botonSecundario} onClick={historial.reintentar}>
              Reintentar
            </button>
          </div>
        )}

        {cargando && entradas.length === 0 && !errorCarga && <p className={styles.vacio}>Cargando…</p>}

        {!cargando && entradas.length === 0 && !errorCarga && (
          <p className={styles.vacio}>
            {hayFiltros
              ? 'No hay cambios con estos filtros.'
              : 'El historial está vacío. Los cambios que se hagan en el diagrama van a aparecer acá.'}
          </p>
        )}

        {entradas.map((entrada) => (
          <Entrada
            key={entrada.id}
            entrada={entrada}
            existe={idsVigentes.has(entrada.id_elemento)}
            avisar={avisoId === entrada.id}
            onTocar={() => handleTocar(entrada)}
          />
        ))}

        {hayAnteriores && entradas.length > 0 && (
          <button
            type="button"
            className={styles.botonSecundario}
            disabled={cargandoMas}
            onClick={handleCargarAnteriores}
          >
            {cargandoMas ? 'Cargando…' : 'Cargar anteriores'}
          </button>
        )}
      </div>
    </div>
  )
}

export default HistorialCambios
