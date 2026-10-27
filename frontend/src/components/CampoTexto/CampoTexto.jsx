import { useState } from 'react'
import styles from './CampoTexto.module.css'

// Campo de los formularios de la app (login, registro, perfil): label visible, ícono a la
// izquierda, botón opcional para mostrar/ocultar la contraseña y error inline.
function CampoTexto({ id, label, icono, type = 'text', error, conToggle = false, ...inputProps }) {
  const [visible, setVisible] = useState(false)
  const tipo = conToggle && visible ? 'text' : type
  const idError = `${id}-error`

  return (
    <div className={styles.campo}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      <div className={`${styles.control} ${error ? styles.controlError : ''}`}>
        <i className={`ti ${icono} ${styles.icono}`} aria-hidden="true" />
        <input
          id={id}
          type={tipo}
          className={styles.input}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? idError : undefined}
          {...inputProps}
        />
        {conToggle && (
          <button
            type="button"
            className={styles.toggle}
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
          >
            <i className={`ti ${visible ? 'ti-eye-off' : 'ti-eye'}`} />
          </button>
        )}
      </div>
      {error && (
        <p id={idError} className={styles.error}>
          {error}
        </p>
      )}
    </div>
  )
}

export default CampoTexto
