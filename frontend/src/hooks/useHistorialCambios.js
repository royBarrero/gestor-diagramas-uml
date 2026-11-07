import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/api'

const LIMITE = 50
const SIN_FILTROS = { usuarioId: '', claseId: '' }

function parametros({ usuarioId, claseId }, extra) {
  return {
    limite: LIMITE,
    ...(usuarioId ? { usuario_id: usuarioId } : {}),
    ...(claseId ? { clase_id: claseId } : {}),
    ...extra,
  }
}

function coincide(entrada, { usuarioId, claseId }) {
  if (usuarioId && entrada.autor_id !== Number(usuarioId)) return false
  return !claseId || entrada.id_elemento === claseId || entrada.ids_clases.includes(claseId)
}

function agregarOpcion(lista, id, nombre, extra) {
  if (lista.some((o) => o.id === id)) return lista
  return [...lista, { id, nombre, ...extra }].sort((a, b) => a.nombre.localeCompare(b.nombre))
}

// CU18: historial de cambios del proyecto. No se pide nada hasta abrir la pestaña por
// primera vez; lo nuevo llega por el socket de useColaboracion.
export function useHistorialCambios(proyectoId, socket, activo) {
  const [entradas, setEntradas] = useState([])
  const [filtros, setFiltros] = useState(SIN_FILTROS)
  const [opciones, setOpciones] = useState({ integrantes: [], clases: [] })
  const [cargando, setCargando] = useState(true)
  const [hayAnteriores, setHayAnteriores] = useState(false)
  const [errorCarga, setErrorCarga] = useState(false)

  const filtrosRef = useRef(filtros)
  const pedidoRef = useRef(0)
  const yaCargadoRef = useRef(false)

  const cargar = useCallback(async () => {
    const pedido = ++pedidoRef.current
    const vigentes = filtrosRef.current
    try {
      const { data } = await api.get(`/proyectos/${proyectoId}/historial`, { params: parametros(vigentes) })
      // Cambiaron los filtros mientras tanto: esta respuesta ya no sirve.
      if (pedido !== pedidoRef.current) return
      const ultimo = data[0]?.id ?? 0
      // Lo que llegó por el socket mientras se esperaba la respuesta no se pierde.
      setEntradas((actuales) => [...actuales.filter((e) => e.id > ultimo && coincide(e, vigentes)), ...data])
      setHayAnteriores(data.length === LIMITE)
      setErrorCarga(false)
    } catch {
      if (pedido === pedidoRef.current) setErrorCarga(true)
    } finally {
      if (pedido === pedidoRef.current) setCargando(false)
    }
  }, [proyectoId])

  const cargarOpciones = useCallback(async () => {
    try {
      const { data } = await api.get(`/proyectos/${proyectoId}/historial/filtros`)
      setOpciones(data)
    } catch {
      // Sin esto los filtros muestran las clases del lienzo y lo que vaya llegando.
    }
  }, [proyectoId])

  useEffect(() => {
    if (!activo || yaCargadoRef.current) return
    yaCargadoRef.current = true
    cargar()
    cargarOpciones()
  }, [activo, cargar, cargarOpciones])

  useEffect(() => {
    if (!socket) return undefined

    function alRecibir(entrada) {
      if (entrada.id_proyecto !== Number(proyectoId) || !yaCargadoRef.current) return
      if (coincide(entrada, filtrosRef.current)) {
        setEntradas((actuales) => (actuales.some((e) => e.id === entrada.id) ? actuales : [entrada, ...actuales]))
      }
      setOpciones((actuales) => ({
        integrantes: agregarOpcion(actuales.integrantes, entrada.autor_id, entrada.autor_nombre, {
          color: entrada.autor_color,
        }),
        clases: entrada.id_elemento
          ? agregarOpcion(actuales.clases, entrada.id_elemento, entrada.nombre_elemento ?? '')
          : actuales.clases,
      }))
    }

    // Lo que pasó sin conexión no llegó: se vuelve a pedir.
    function alConectar() {
      if (yaCargadoRef.current) cargar()
    }

    socket.on('historial_cambio', alRecibir)
    socket.on('connect', alConectar)
    return () => {
      socket.off('historial_cambio', alRecibir)
      socket.off('connect', alConectar)
    }
  }, [socket, proyectoId, cargar])

  function cambiarFiltros(cambios) {
    const nuevos = { ...filtrosRef.current, ...cambios }
    filtrosRef.current = nuevos
    setFiltros(nuevos)
    setEntradas([])
    setCargando(true)
    setErrorCarga(false)
    setHayAnteriores(false)
    cargar()
  }

  function reintentar() {
    setCargando(true)
    setErrorCarga(false)
    cargar()
  }

  async function cargarAnteriores() {
    const vigentes = filtrosRef.current
    const pedido = pedidoRef.current
    try {
      const { data } = await api.get(`/proyectos/${proyectoId}/historial`, {
        params: parametros(vigentes, { antes_de: entradas[entradas.length - 1].id }),
      })
      if (pedido !== pedidoRef.current) return
      setEntradas((actuales) => {
        const ids = new Set(actuales.map((e) => e.id))
        return [...actuales, ...data.filter((e) => !ids.has(e.id))]
      })
      setHayAnteriores(data.length === LIMITE)
    } catch {
      if (pedido === pedidoRef.current) setErrorCarga(true)
    }
  }

  return { entradas, filtros, opciones, cargando, hayAnteriores, errorCarga, cambiarFiltros, cargarAnteriores, reintentar }
}
