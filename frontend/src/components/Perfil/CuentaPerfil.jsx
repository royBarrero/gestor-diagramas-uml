import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { api } from '../../services/api'
import CampoTexto from '../CampoTexto/CampoTexto'
import styles from './CuentaPerfil.module.css'

function Aviso({ aviso }) {
  if (!aviso) return null
  const esError = aviso.tipo === 'error'
  return (
    <p className={esError ? styles.avisoError : styles.avisoExito} role={esError ? 'alert' : 'status'}>
      <i className={`ti ${esError ? 'ti-alert-circle' : 'ti-circle-check'}`} aria-hidden="true" />
      {aviso.texto}
    </p>
  )
}

// Sección "Cuenta" del perfil: editar nombre y cambiar contraseña.
function CuentaPerfil() {
  const { usuario, setUsuario } = useAuth()

  const [nombre, setNombre] = useState(usuario.nombre)
  const [guardandoNombre, setGuardandoNombre] = useState(false)
  const [avisoNombre, setAvisoNombre] = useState(null)

  const [passwordActual, setPasswordActual] = useState('')
  const [passwordNueva, setPasswordNueva] = useState('')
  const [confirmarPassword, setConfirmarPassword] = useState('')
  const [guardandoPassword, setGuardandoPassword] = useState(false)
  const [avisoPassword, setAvisoPassword] = useState(null)

  const nombreLimpio = nombre.trim()
  const nombreCambio = nombreLimpio !== '' && nombreLimpio !== usuario.nombre
  const passwordsNoCoinciden = confirmarPassword !== '' && confirmarPassword !== passwordNueva

  async function handleGuardarNombre(event) {
    event.preventDefault()
    if (!nombreCambio) return
    setAvisoNombre(null)
    setGuardandoNombre(true)
    try {
      const { data } = await api.put('/auth/me', { nombre: nombreLimpio })
      setUsuario(data)
      setNombre(data.nombre)
      setAvisoNombre({ tipo: 'exito', texto: 'Nombre actualizado.' })
    } catch (err) {
      setAvisoNombre({ tipo: 'error', texto: err.response?.data?.detail ?? 'No se pudo actualizar el nombre.' })
    } finally {
      setGuardandoNombre(false)
    }
  }

  async function handleCambiarPassword(event) {
    event.preventDefault()
    if (passwordsNoCoinciden) return
    setAvisoPassword(null)
    setGuardandoPassword(true)
    try {
      await api.put('/auth/me/password', {
        password_actual: passwordActual,
        password_nueva: passwordNueva,
      })
      setPasswordActual('')
      setPasswordNueva('')
      setConfirmarPassword('')
      setAvisoPassword({ tipo: 'exito', texto: 'Contraseña actualizada.' })
    } catch (err) {
      setAvisoPassword({
        tipo: 'error',
        texto: err.response?.data?.detail ?? 'No se pudo cambiar la contraseña.',
      })
    } finally {
      setGuardandoPassword(false)
    }
  }

  return (
    <div className={styles.cuenta}>
      <form className={styles.bloque} onSubmit={handleGuardarNombre}>
        <div className={styles.bloqueTexto}>
          <h3 className={styles.bloqueTitulo}>Nombre visible</h3>
          <p className={styles.bloqueDescripcion}>Es el nombre que ven tus compañeros en los proyectos.</p>
        </div>
        <div className={styles.filaNombre}>
          <CampoTexto
            id="perfil-nombre"
            label="Nombre"
            icono="ti-user"
            autoComplete="name"
            value={nombre}
            onChange={(event) => {
              setNombre(event.target.value)
              setAvisoNombre(null)
            }}
            required
          />
          <button type="submit" className={styles.botonPrimario} disabled={!nombreCambio || guardandoNombre}>
            {guardandoNombre ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
        <Aviso aviso={avisoNombre} />
      </form>

      <form className={styles.bloque} onSubmit={handleCambiarPassword}>
        <div className={styles.bloqueTexto}>
          <h3 className={styles.bloqueTitulo}>Cambiar contraseña</h3>
          <p className={styles.bloqueDescripcion}>Necesitás tu contraseña actual para confirmar el cambio.</p>
        </div>
        <CampoTexto
          id="perfil-password-actual"
          label="Contraseña actual"
          icono="ti-lock"
          type="password"
          autoComplete="current-password"
          conToggle
          value={passwordActual}
          onChange={(event) => setPasswordActual(event.target.value)}
          required
        />
        <div className={styles.filaPasswords}>
          <CampoTexto
            id="perfil-password-nueva"
            label="Contraseña nueva"
            icono="ti-lock-plus"
            type="password"
            placeholder="Elegí una contraseña"
            autoComplete="new-password"
            conToggle
            value={passwordNueva}
            onChange={(event) => setPasswordNueva(event.target.value)}
            required
          />
          <CampoTexto
            id="perfil-password-confirmar"
            label="Confirmar contraseña nueva"
            icono="ti-lock-check"
            type="password"
            placeholder="Repetí la contraseña"
            autoComplete="new-password"
            value={confirmarPassword}
            onChange={(event) => setConfirmarPassword(event.target.value)}
            error={passwordsNoCoinciden ? 'Las contraseñas no coinciden.' : null}
            required
          />
        </div>
        <Aviso aviso={avisoPassword} />
        <button
          type="submit"
          className={`${styles.botonPrimario} ${styles.botonDerecha}`}
          disabled={guardandoPassword}
        >
          {guardandoPassword ? 'Actualizando...' : 'Actualizar contraseña'}
        </button>
      </form>
    </div>
  )
}

export default CuentaPerfil
