import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/AuthLayout/AuthLayout'
import { api } from '../../services/api'
import styles from './Registro.module.css'

function Registro() {
  const navigate = useNavigate()
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [cargando, setCargando] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
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
    <AuthLayout titulo="Crear cuenta" subtitulo="Empezá a diagramar en minutos.">
      <form className={styles.form} onSubmit={handleSubmit}>
        <label className={styles.label} htmlFor="nombre">
          Nombre
        </label>
        <input
          id="nombre"
          type="text"
          className={styles.input}
          value={nombre}
          onChange={(event) => setNombre(event.target.value)}
          required
        />

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
          {cargando ? 'Creando cuenta...' : 'Crear cuenta'}
        </button>

        {error && <p className={styles.error}>{error}</p>}
      </form>

      <p className={styles.linkTexto}>
        ¿Ya tenés cuenta? <Link to="/login">Iniciá sesión</Link>
      </p>
    </AuthLayout>
  )
}

export default Registro
