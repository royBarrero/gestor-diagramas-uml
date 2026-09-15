import { Component } from 'react'
import styles from './ErrorBoundaryLienzo.module.css'

class ErrorBoundaryLienzo extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Error renderizando el lienzo de la pizarra:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className={styles.contenedor}>
          <p className={styles.titulo}>Ocurrió un error mostrando el lienzo.</p>
          <p className={styles.detalle}>{this.state.error.message}</p>
          <p className={styles.ayuda}>Recargá la página. Si vuelve a pasar, revisá la consola (F12) para más detalle.</p>
        </div>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundaryLienzo
