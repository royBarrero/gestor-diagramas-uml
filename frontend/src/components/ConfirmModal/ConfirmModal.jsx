import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import styles from './ConfirmModal.module.css'

// Modal de confirmación genérico. `variante="peligro"` lo pinta en coral para
// acciones destructivas; `detalles` ([{ icono, texto }]) lista lo que se afecta.
// Si `onConfirm` devuelve una promesa, el modal muestra `textoProcesando`
// y bloquea los botones hasta que termine.
function ConfirmModal({
  titulo,
  mensaje,
  onConfirm,
  onCancel,
  variante = 'normal',
  icono,
  textoConfirmar = 'Confirmar',
  textoProcesando = 'Procesando...',
  detalles,
}) {
  const [procesando, setProcesando] = useState(false)
  const esPeligro = variante === 'peligro'
  const iconoFinal = icono ?? (esPeligro ? 'ti-alert-triangle' : 'ti-help-circle')

  useEffect(() => {
    function handleTecla(event) {
      if (event.key === 'Escape' && !procesando) onCancel()
    }
    document.addEventListener('keydown', handleTecla)
    return () => document.removeEventListener('keydown', handleTecla)
  }, [procesando, onCancel])

  async function handleConfirmar() {
    const resultado = onConfirm()
    if (resultado && typeof resultado.then === 'function') {
      setProcesando(true)
      try {
        await resultado
      } finally {
        setProcesando(false)
      }
    }
  }

  return createPortal(
    <div
      className={styles.overlay}
      onClick={(event) => {
        // Evita que el clic llegue a un modal padre (ej. MiembrosModal) a través del portal.
        event.stopPropagation()
        if (!procesando) onCancel()
      }}
    >
      <div
        className={styles.modal}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titulo ? 'confirm-titulo' : undefined}
        aria-describedby="confirm-mensaje"
        onClick={(event) => event.stopPropagation()}
      >
        <span className={esPeligro ? styles.iconoPeligro : styles.icono} aria-hidden="true">
          <i className={`ti ${iconoFinal}`} />
        </span>

        {titulo && (
          <h2 id="confirm-titulo" className={styles.titulo}>
            {titulo}
          </h2>
        )}
        <p id="confirm-mensaje" className={styles.mensaje}>
          {mensaje}
        </p>

        {detalles?.length > 0 && (
          <ul className={esPeligro ? styles.detallesPeligro : styles.detalles}>
            {detalles.map((detalle) => (
              <li key={detalle.texto}>
                <i className={`ti ${detalle.icono}`} aria-hidden="true" />
                {detalle.texto}
              </li>
            ))}
          </ul>
        )}

        <div className={styles.acciones}>
          <button type="button" className={styles.botonCancelar} onClick={onCancel} disabled={procesando}>
            Cancelar
          </button>
          <button
            type="button"
            className={esPeligro ? styles.botonPeligro : styles.botonConfirmar}
            onClick={handleConfirmar}
            disabled={procesando}
            autoFocus
          >
            {procesando ? textoProcesando : textoConfirmar}
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

export default ConfirmModal
