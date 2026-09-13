import styles from './AuthLayout.module.css'

function UmlIllustration() {
  return (
    <svg viewBox="0 0 260 160" className={styles.illustration} role="presentation" aria-hidden="true">
      <rect x="10" y="20" width="90" height="60" rx="4" fill="none" stroke="var(--border)" strokeWidth="1.5" />
      <line x1="10" y1="40" x2="100" y2="40" stroke="var(--border)" strokeWidth="1.5" />
      <line x1="10" y1="58" x2="100" y2="58" stroke="var(--border)" strokeWidth="1.5" />

      <rect x="160" y="80" width="90" height="60" rx="4" fill="none" stroke="var(--border)" strokeWidth="1.5" />
      <line x1="160" y1="100" x2="250" y2="100" stroke="var(--border)" strokeWidth="1.5" />
      <line x1="160" y1="118" x2="250" y2="118" stroke="var(--border)" strokeWidth="1.5" />

      <line
        x1="100"
        y1="60"
        x2="160"
        y2="100"
        stroke="var(--accent)"
        strokeWidth="1.5"
        strokeDasharray="4 4"
      />
      <polygon points="160,100 168,96 160,92" fill="var(--accent)" />
    </svg>
  )
}

function AuthLayout({ titulo, subtitulo, children }) {
  return (
    <div className={styles.container}>
      <div className={`${styles.panelIzquierdo} grid-bg`}>
        <span className={styles.marca}>gestor-diagramas-uml</span>
        <p className={styles.tagline}>Diagramas de clases UML, en equipo, en tiempo real.</p>
        <UmlIllustration />
      </div>

      <div className={styles.panelDerecho}>
        <div className={styles.formWrapper}>
          <h1 className={styles.titulo}>{titulo}</h1>
          {subtitulo && <p className={styles.subtitulo}>{subtitulo}</p>}
          {children}
        </div>
      </div>
    </div>
  )
}

export default AuthLayout
