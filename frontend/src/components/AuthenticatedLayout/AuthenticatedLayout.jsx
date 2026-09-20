import { Navigate, Outlet } from 'react-router-dom'
import { AuthProvider } from '../../contexts/AuthContext'
import AsistenteFlotante from '../Asistente/AsistenteFlotante'

function AuthenticatedLayout() {
  const token = localStorage.getItem('access_token')

  if (!token) {
    return <Navigate to="/login" replace />
  }

  return (
    <AuthProvider>
      <Outlet />
      <AsistenteFlotante />
    </AuthProvider>
  )
}

export default AuthenticatedLayout
