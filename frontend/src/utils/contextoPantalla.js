// CU13: descripción corta de "en qué pantalla está el usuario", enviada al
// agente asistente como contexto — no hace falta nada más elaborado que un
// mapeo estático de rutas, el agente orienta sobre el USO del sistema, no
// sobre el contenido puntual de un diagrama.
const PANTALLAS = [
  {
    patron: /^\/dashboard/,
    descripcion: 'Dashboard: listado de proyectos del usuario, crear/administrar proyectos e invitar colaboradores.',
  },
  {
    patron: /^\/perfil/,
    descripcion: 'Perfil de usuario: datos de la cuenta.',
  },
  {
    patron: /^\/proyecto\/.+\/pizarra/,
    descripcion:
      'Editor de diagramas de clases (Pizarra): crear clases con atributos y métodos, relaciones entre ' +
      'clases, exportar/importar, comando de voz, digitalizar por foto, generar backend/frontend.',
  },
]

export function contextoPantalla(pathname) {
  const pantalla = PANTALLAS.find((p) => p.patron.test(pathname))
  return pantalla?.descripcion ?? 'Pantalla no identificada.'
}
