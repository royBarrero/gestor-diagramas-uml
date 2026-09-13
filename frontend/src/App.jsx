import { Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login/Login'
import Registro from './pages/Registro/Registro'
import Dashboard from './pages/Dashboard/Dashboard'
import Perfil from './pages/Perfil/Perfil'
import Pizarra from './pages/Pizarra/Pizarra'
import AuthenticatedLayout from './components/AuthenticatedLayout/AuthenticatedLayout'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/registro" element={<Registro />} />
      <Route element={<AuthenticatedLayout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/perfil" element={<Perfil />} />
        <Route path="/proyecto/:id/pizarra" element={<Pizarra />} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}

export default App
