import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/AuthLayout/AuthLayout'
import CampoTexto from '../../components/CampoTexto/CampoTexto'
import { api } from '../../services/api'
import styles from './Login.module.css'

function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [cargando, setCargando] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setCargando(true)

    try {
      const { data } = await api.post('/auth/login', { email, password })
      localStorage.setItem('access_token', data.access_token)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail ?? 'No se pudo iniciar sesión.')
    } finally {
      setCargando(false)
    }
  }

  return (
    <AuthLayout titulo="Iniciar sesión" subtitulo="Accedé a tus proyectos y diagramas.">
      <form className={styles.form} onSubmit={handleSubmit}>
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
          placeholder="Tu contraseña"
          autoComplete="current-password"
          conToggle
          value={password}
          onChange={(event) => setPassword(event.target.value)}
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
            'Entrando...'
          ) : (
            <>
              Entrar <i className="ti ti-arrow-right" aria-hidden="true" />
            </>
          )}
        </button>
      </form>

      <p className={styles.linkTexto}>
        ¿No tenés cuenta? <Link to="/registro">Registrate</Link>
      </p>
    </AuthLayout>
  )
}

export default Login
