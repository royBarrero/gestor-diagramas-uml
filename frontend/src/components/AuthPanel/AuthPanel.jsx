import styles from './AuthPanel.module.css'

const FUNCIONALIDADES = [
  { icono: 'ti-users', texto: 'Colaborá con tu equipo en tiempo real' },
  { icono: 'ti-microphone', texto: 'Creá clases por voz o desde una foto' },
  { icono: 'ti-code', texto: 'Generá el backend en Spring Boot y el frontend en Flutter' },
]

// Ilustración decorativa: Usuario 1 — 0..* Proyecto.
function DiagramaIlustracion() {
  return (
    <svg viewBox="0 0 330 230" className={styles.diagrama} role="presentation" aria-hidden="true">
      <g className={styles.clase}>
        <rect x="1" y="1" width="118" height="74" rx="5" />
        <line x1="1" y1="23" x2="119" y2="23" />
        <text x="9" y="16" className={styles.nombreClase}>Usuario</text>
        <text x="9" y="38">- id: int</text>
        <text x="9" y="51">- nombre: String</text>
        <text x="9" y="64">- email: String</text>
      </g>

      <polyline points="119,35 166,35 166,77 200,77" className={styles.relacion} />
      <text x="123" y="29" className={styles.multiplicidad}>1</text>
      <text x="183" y="88" className={styles.multiplicidad}>0..*</text>

      <g className={styles.clase} transform="translate(200 49)">
        <rect x="0" y="0" width="118" height="61" rx="5" />
        <line x1="0" y1="22" x2="118" y2="22" />
        <text x="8" y="15" className={styles.nombreClase}>Proyecto</text>
        <text x="8" y="37">- id: int</text>
        <text x="8" y="50">- nombre: String</text>
      </g>
    </svg>
  )
}

function AuthPanel() {
  return (
    <aside className={styles.panel}>
      <div className={styles.marca}>
        <span className={styles.logo}>
          <i className="ti ti-hierarchy-2" />
        </span>
        Gestor de Diagramas UML
      </div>

      <div className={styles.centro}>
        <h2 className={styles.titular}>
          Del diagrama de clases <span className={styles.resaltado}>al código</span>, en equipo.
        </h2>

        <div className={styles.ilustracion}>
          <DiagramaIlustracion />
          <span className={styles.editando}>
            <span className={styles.puntoEditando} /> 2 personas editando
          </span>
        </div>

        <ul className={styles.funcionalidades}>
          {FUNCIONALIDADES.map((funcionalidad) => (
            <li key={funcionalidad.icono}>
              <span className={styles.iconoFuncionalidad}>
                <i className={`ti ${funcionalidad.icono}`} />
              </span>
              {funcionalidad.texto}
            </li>
          ))}
        </ul>
      </div>

      <span className={styles.pie}>Ingeniería de Software I · UAGRM</span>
    </aside>
  )
}

export default AuthPanel
