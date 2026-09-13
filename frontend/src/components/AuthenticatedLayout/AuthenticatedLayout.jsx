import { Navigate, Outlet } from 'react-router-dom'
import { AuthProvider } from '../../contexts/AuthContext'

function AuthenticatedLayout() {
  const token = localStorage.getItem('access_token')

  if (!token) {
    return <Navigate to="/login" replace />
  }

  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}

export default AuthenticatedLayout
