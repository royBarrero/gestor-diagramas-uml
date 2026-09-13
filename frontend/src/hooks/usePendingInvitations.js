import { useEffect, useState } from 'react'
import { api } from '../services/api'

export function usePendingInvitations() {
  const [invitaciones, setInvitaciones] = useState([])
  const [cargando, setCargando] = useState(true)

  function recargar() {
    api
      .get('/invitaciones/pendientes')
      .then(({ data }) => setInvitaciones(data))
      .finally(() => setCargando(false))
  }

  useEffect(() => {
    recargar()
  }, [])

  return { invitaciones, cargando, recargar }
}
