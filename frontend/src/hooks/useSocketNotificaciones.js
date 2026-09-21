import { useEffect, useRef } from 'react'
import { io } from 'socket.io-client'
import { SOCKET_URL } from './useColaboracion'

export function useSocketNotificaciones(eventos) {
  const eventosRef = useRef(eventos)

  useEffect(() => {
    eventosRef.current = eventos
  })

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) return undefined

    const socket = io(SOCKET_URL, { auth: { token } })
    const nombres = Object.keys(eventosRef.current)
    const manejadores = nombres.map((nombre) => (payload) => eventosRef.current[nombre]?.(payload))
    nombres.forEach((nombre, i) => socket.on(nombre, manejadores[i]))

    return () => {
      nombres.forEach((nombre, i) => socket.off(nombre, manejadores[i]))
      socket.disconnect()
    }
  }, [])
}
