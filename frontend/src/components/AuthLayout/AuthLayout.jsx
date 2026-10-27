import AuthPanel from '../AuthPanel/AuthPanel'
import styles from './AuthLayout.module.css'

function AuthLayout({ titulo, subtitulo, children }) {
  return (
    <div className={styles.container}>
      <AuthPanel />

      <main className={styles.panelDerecho}>
        <div className={styles.formWrapper}>
          <h1 className={styles.titulo}>{titulo}</h1>
          {subtitulo && <p className={styles.subtitulo}>{subtitulo}</p>}
          {children}
        </div>
      </main>
    </div>
  )
}

export default AuthLayout
