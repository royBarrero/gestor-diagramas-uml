import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/AuthLayout/AuthLayout'
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
        <label className={styles.label} htmlFor="email">
          Correo
        </label>
        <input
          id="email"
          type="email"
          className={styles.input}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <label className={styles.label} htmlFor="password">
          Contraseña
        </label>
        <input
          id="password"
          type="password"
          className={styles.input}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        <button type="submit" className={styles.boton} disabled={cargando}>
          {cargando ? 'Entrando...' : 'Entrar'}
        </button>

        {error && <p className={styles.error}>{error}</p>}
      </form>

      <p className={styles.linkTexto}>
        ¿No tenés cuenta? <Link to="/registro">Registrate</Link>
      </p>
    </AuthLayout>
  )
}

export default Login
