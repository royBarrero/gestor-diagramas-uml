import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../services/api'
import { huellaClase } from '../utils/huellaClase'

const MS_AVISO_ABIERTO = 12000

function claveSilencio(usuarioId) {
  return `ia_silenciada_${usuarioId}`
}

function leerSilencio(usuarioId) {
  try {
    return localStorage.getItem(claveSilencio(usuarioId)) === '1'
  } catch {
    return false
  }
}

function guardarSilencio(usuarioId, activo) {
  try {
    localStorage.setItem(claveSilencio(usuarioId), activo ? '1' : '0')
  } catch {
    // Sin almacenamiento el silencio dura solo hasta recargar.
  }
}

// CU16: sugerencias del agente sobre las clases de la pizarra. Las marcas viven
// solo en esta sesión; la sugerencia en sí queda en el historial del chat. Cada
// marca guarda la huella de la clase al llegar: si la clase cambia, deja de
// mostrarse, porque la sugerencia ya se refiere a una versión anterior.
export function useSugerenciasIA({ socket, proyectoId, usuarioId, nodes, edges, seleccionId }) {
  const [marcas, setMarcas] = useState({}) // claseId -> marca
  const [avisoClaseId, setAvisoClaseId] = useState(null)
  const [avisoEnPausa, setAvisoEnPausa] = useState(false)
  // El usuario se carga después de montar la pizarra: mientras no haya un cambio
  // hecho en esta sesión, se usa lo guardado para ese usuario.
  const [silencioElegido, setSilencioElegido] = useState(null)
  const silenciado = silencioElegido ?? (usuarioId ? leerSilencio(usuarioId) : false)

  const nodesRef = useRef(nodes)
  const edgesRef = useRef(edges)
  const avisoRef = useRef(null)

  useEffect(() => {
    nodesRef.current = nodes
    edgesRef.current = edges
  }, [nodes, edges])

  const marcasVigentes = useMemo(() => {
    const vigentes = {}
    Object.entries(marcas).forEach(([claseId, marca]) => {
      if (huellaClase(nodes, edges, claseId) === marca.huella) vigentes[claseId] = marca
    })
    return vigentes
  }, [marcas, nodes, edges])

  const marcaAviso = avisoClaseId ? marcasVigentes[avisoClaseId] : undefined
  const aviso = marcaAviso?.destinoId === usuarioId ? { claseId: avisoClaseId, ...marcaAviso } : null

  useEffect(() => {
    avisoRef.current = aviso?.claseId ?? null
  }, [aviso?.claseId])

  useEffect(() => {
    if (!socket) return undefined

    function alRecibirMensaje(mensaje) {
      // Los mensajes con `accion` son resúmenes de cambios (CU17), no sugerencias.
      if (mensaje.tipo !== 'agente' || !mensaje.elemento_referenciado || mensaje.accion) return
      if (mensaje.id_proyecto !== Number(proyectoId)) return

      const claseId = mensaje.elemento_referenciado
      const huella = huellaClase(nodesRef.current, edgesRef.current, claseId)
      if (huella === null) return

      setMarcas((actuales) => ({
        ...actuales,
        [claseId]: {
          mensajeId: mensaje.id,
          texto: mensaje.texto,
          destinoId: mensaje.destino_id,
          destinoNombre: mensaje.destino_nombre,
          huella,
        },
      }))
      // Máximo un aviso abierto: las demás quedan en el chat y suman al contador.
      if (mensaje.destino_id === usuarioId && !avisoRef.current) {
        avisoRef.current = claseId
        setAvisoClaseId(claseId)
        setAvisoEnPausa(false)
      }
    }

    // Una sugerencia corregida (CU17) deja de marcarse.
    function alActualizarMensaje(mensaje) {
      if (!mensaje.sugerencia_resuelta) return
      setMarcas((actuales) => {
        const quedan = Object.entries(actuales).filter(([, marca]) => marca.mensajeId !== mensaje.id)
        return quedan.length === Object.keys(actuales).length ? actuales : Object.fromEntries(quedan)
      })
    }

    socket.on('chat_mensaje', alRecibirMensaje)
    socket.on('chat_mensaje_actualizado', alActualizarMensaje)
    return () => {
      socket.off('chat_mensaje', alRecibirMensaje)
      socket.off('chat_mensaje_actualizado', alActualizarMensaje)
    }
  }, [socket, proyectoId, usuarioId])

  // El servidor guarda el silencio en memoria: se le repite en cada conexión.
  useEffect(() => {
    if (!socket || !usuarioId) return undefined

    function avisarSilencio() {
      socket.emit('silenciar_ia', { activo: silenciado })
    }

    socket.on('connect', avisarSilencio)
    if (socket.connected) avisarSilencio()
    return () => socket.off('connect', avisarSilencio)
  }, [socket, usuarioId, silenciado])

  // Sin respuesta, el aviso se reduce al icono de alerta de la clase.
  const avisoAbiertoId = aviso?.claseId ?? null
  useEffect(() => {
    if (!avisoAbiertoId || avisoEnPausa) return undefined
    const temporizador = setTimeout(() => setAvisoClaseId(null), MS_AVISO_ABIERTO)
    return () => clearTimeout(temporizador)
  }, [avisoAbiertoId, avisoEnPausa])

  // Solo reacciona a un cambio de selección: una sugerencia puede llegar cuando
  // el usuario ya está en otra clase, y ese aviso igual tiene que abrirse.
  useEffect(() => {
    if (seleccionId && avisoRef.current && avisoRef.current !== seleccionId) {
      setAvisoClaseId(null)
    }
  }, [seleccionId])

  const abrirAviso = useCallback((claseId) => {
    setAvisoEnPausa(false)
    setAvisoClaseId(claseId)
  }, [])

  const cerrarAviso = useCallback(() => setAvisoClaseId(null), [])

  const ignorar = useCallback((claseId) => {
    setAvisoClaseId(null)
    setMarcas((actuales) => {
      const resto = { ...actuales }
      delete resto[claseId]
      return resto
    })
  }, [])

  // CU17: le pide al agente que aplique la sugerencia. Devuelve el motivo si no se pudo.
  async function pedirCorreccion(mensajeId) {
    try {
      await api.post(`/proyectos/${proyectoId}/mensajes/${mensajeId}/pedir-correccion`)
      return null
    } catch (error) {
      const detalle = error.response?.data?.detail
      return typeof detalle === 'string' ? detalle : 'No se pudo pedir la corrección.'
    }
  }

  function alternarSilencio() {
    setSilencioElegido(!silenciado)
    guardarSilencio(usuarioId, !silenciado)
  }

  return {
    marcas: marcasVigentes,
    aviso,
    abrirAviso,
    cerrarAviso,
    ignorar,
    pausarAviso: setAvisoEnPausa,
    pedirCorreccion,
    silenciado,
    alternarSilencio,
  }
}
