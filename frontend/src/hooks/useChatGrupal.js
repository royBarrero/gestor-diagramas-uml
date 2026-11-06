import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../services/api'

const LIMITE_HISTORIAL = 50
const LIMITE_RECONEXION = 200

// CU15: chat grupal del proyecto. El historial y el envío van por REST; los
// mensajes nuevos llegan por el socket de useColaboracion. Un mismo mensaje
// puede llegar por las dos vías, así que se unen por id.
export function useChatGrupal(proyectoId, socket, abierto) {
  const { usuario } = useAuth()
  const [mensajes, setMensajes] = useState([])
  const [noLeidos, setNoLeidos] = useState(0)
  const [agenteEscribiendo, setAgenteEscribiendo] = useState(false)
  const [hayAnteriores, setHayAnteriores] = useState(false)
  const [errorCarga, setErrorCarga] = useState(false)
  const [errorEnvio, setErrorEnvio] = useState(null)
  const [enviando, setEnviando] = useState(false)

  const idsRef = useRef(new Set())
  const abiertoRef = useRef(abierto)
  const usuarioIdRef = useRef(usuario?.id)

  useEffect(() => {
    abiertoRef.current = abierto
  }, [abierto])

  useEffect(() => {
    usuarioIdRef.current = usuario?.id
  }, [usuario?.id])

  const incorporar = useCallback((lista, { contar }) => {
    const nuevos = lista.filter((m) => !idsRef.current.has(m.id))
    nuevos.forEach((m) => idsRef.current.add(m.id))
    if (contar && !abiertoRef.current) {
      const ajenos = nuevos.filter((m) => m.autor_id !== usuarioIdRef.current).length
      if (ajenos > 0) setNoLeidos((n) => n + ajenos)
    }
    // Siempre un arreglo nuevo: el panel ajusta el scroll al cambiar la lista.
    setMensajes((actuales) => [...actuales, ...nuevos].sort((a, b) => a.id - b.id))
  }, [])

  const ultimoId = useCallback(() => (idsRef.current.size ? Math.max(...idsRef.current) : null), [])

  const cargarUltimos = useCallback(
    () =>
      api
        .get(`/proyectos/${proyectoId}/mensajes`, { params: { limite: LIMITE_HISTORIAL } })
        .then(({ data }) => {
          incorporar(data, { contar: false })
          setHayAnteriores(data.length === LIMITE_HISTORIAL)
          setErrorCarga(false)
        })
        .catch(() => setErrorCarga(true)),
    [proyectoId, incorporar]
  )

  // Al reconectar, trae todo lo posterior al último mensaje recibido.
  const ponerseAlDia = useCallback(async () => {
    let desde = ultimoId()
    if (desde === null) return cargarUltimos()
    try {
      for (;;) {
        const { data } = await api.get(`/proyectos/${proyectoId}/mensajes`, {
          params: { despues_de: desde, limite: LIMITE_RECONEXION },
        })
        incorporar(data, { contar: true })
        if (data.length < LIMITE_RECONEXION) break
        desde = data[data.length - 1].id
      }
      setErrorCarga(false)
    } catch {
      setErrorCarga(true)
    }
  }, [proyectoId, incorporar, ultimoId, cargarUltimos])

  useEffect(() => {
    cargarUltimos()
  }, [cargarUltimos])

  useEffect(() => {
    if (!socket) return undefined

    function alConectar() {
      setAgenteEscribiendo(false)
      ponerseAlDia()
    }
    function alRecibirMensaje(mensaje) {
      if (mensaje.id_proyecto === Number(proyectoId)) incorporar([mensaje], { contar: true })
    }
    function alCambiarEscritura({ activo }) {
      setAgenteEscribiendo(activo)
    }

    socket.on('connect', alConectar)
    socket.on('chat_mensaje', alRecibirMensaje)
    socket.on('chat_agente_escribiendo', alCambiarEscritura)
    return () => {
      socket.off('connect', alConectar)
      socket.off('chat_mensaje', alRecibirMensaje)
      socket.off('chat_agente_escribiendo', alCambiarEscritura)
    }
  }, [socket, proyectoId, incorporar, ponerseAlDia])

  // Devuelve true si salió bien; si falla, el panel deja el texto en la caja.
  async function enviar(texto) {
    setEnviando(true)
    setErrorEnvio(null)
    try {
      const { data } = await api.post(`/proyectos/${proyectoId}/mensajes`, { texto })
      incorporar([data], { contar: false })
      return true
    } catch (error) {
      const detalle = error.response?.data?.detail
      setErrorEnvio(typeof detalle === 'string' ? detalle : 'No se pudo enviar el mensaje.')
      return false
    } finally {
      setEnviando(false)
    }
  }

  // Devuelve true si salió bien.
  async function cargarAnteriores() {
    try {
      const { data } = await api.get(`/proyectos/${proyectoId}/mensajes`, {
        params: { antes_de: Math.min(...idsRef.current), limite: LIMITE_HISTORIAL },
      })
      incorporar(data, { contar: false })
      setHayAnteriores(data.length === LIMITE_HISTORIAL)
      return true
    } catch {
      setErrorCarga(true)
      return false
    }
  }

  return {
    mensajes,
    noLeidos,
    agenteEscribiendo,
    hayAnteriores,
    errorCarga,
    errorEnvio,
    enviando,
    enviar,
    cargarAnteriores,
    reintentarCarga: ponerseAlDia,
    marcarLeidos: () => setNoLeidos(0),
  }
}
