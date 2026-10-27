import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/AuthLayout/AuthLayout'
import CampoTexto from '../../components/CampoTexto/CampoTexto'
import { api } from '../../services/api'
import styles from './Registro.module.css'

function Registro() {
  const navigate = useNavigate()
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmarPassword, setConfirmarPassword] = useState('')
  const [error, setError] = useState(null)
  const [cargando, setCargando] = useState(false)

  // Validación solo en el navegador: confirmarPassword no se envía al backend.
  const passwordsNoCoinciden = confirmarPassword !== '' && confirmarPassword !== password

  async function handleSubmit(event) {
    event.preventDefault()
    if (passwordsNoCoinciden) return
    setError(null)
    setCargando(true)

    try {
      await api.post('/auth/registro', { nombre, email, password })
      navigate('/login')
    } catch (err) {
      setError(err.response?.data?.detail ?? 'No se pudo crear la cuenta.')
    } finally {
      setCargando(false)
    }
  }

  return (
    <AuthLayout titulo="Crear cuenta" subtitulo="Registrate para crear proyectos o sumarte a uno.">
      <form className={styles.form} onSubmit={handleSubmit}>
        <CampoTexto
          id="nombre"
          label="Nombre"
          icono="ti-user"
          placeholder="Tu nombre completo"
          autoComplete="name"
          value={nombre}
          onChange={(event) => setNombre(event.target.value)}
          required
        />

        <CampoTexto
          id="email"
          label="Correo"
          icono="ti-mail"
          type="email"
          placeholder="tu@correo.com"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <CampoTexto
          id="password"
          label="Contraseña"
          icono="ti-lock"
          type="password"
          placeholder="Elegí una contraseña"
          autoComplete="new-password"
          conToggle
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        <CampoTexto
          id="confirmar-password"
          label="Confirmar contraseña"
          icono="ti-lock"
          type="password"
          placeholder="Repetí la contraseña"
          autoComplete="new-password"
          value={confirmarPassword}
          onChange={(event) => setConfirmarPassword(event.target.value)}
          error={passwordsNoCoinciden ? 'Las contraseñas no coinciden.' : null}
          required
        />

        {error && (
          <p className={styles.error} role="alert">
            <i className="ti ti-alert-circle" aria-hidden="true" />
            {error}
          </p>
        )}

        <button type="submit" className={styles.boton} disabled={cargando}>
          {cargando ? (
            'Creando cuenta...'
          ) : (
            <>
              Crear cuenta <i className="ti ti-arrow-right" aria-hidden="true" />
            </>
          )}
        </button>
      </form>

      <p className={styles.linkTexto}>
        ¿Ya tenés cuenta? <Link to="/login">Iniciá sesión</Link>
      </p>
    </AuthLayout>
  )
}

export default Registro
