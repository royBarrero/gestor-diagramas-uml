// CU13: descripción corta de "en qué pantalla está el usuario", enviada al
// agente asistente como contexto — no hace falta nada más elaborado que un
// mapeo estático de rutas, el agente orienta sobre el USO del sistema, no
// sobre el contenido puntual de un diagrama. Cada pantalla trae además
// preguntas sugeridas que el chat muestra cuando la conversación está vacía.
const PANTALLAS = [
  {
    patron: /^\/dashboard/,
    descripcion:
      'Dashboard ("Tus proyectos"): tarjetas de proyectos con botones Abrir y Generar, y menú ⋮ ' +
      '(Editar / Miembros / Eliminar); botón Nuevo proyecto y filtros por rol.',
    sugerencias: [
      '¿Cómo invito a un colaborador?',
      '¿Cómo genero el backend de un proyecto?',
      '¿Qué diferencia hay entre administrador y colaborador?',
    ],
  },
  {
    patron: /^\/perfil/,
    descripcion:
      'Perfil de usuario: datos de la cuenta, estadísticas, invitaciones pendientes, actividad reciente, ' +
      'cambiar el nombre y la contraseña.',
    sugerencias: [
      '¿Cómo acepto una invitación?',
      '¿Cómo cambio mi contraseña?',
    ],
  },
  {
    patron: /^\/proyecto\/.+\/pizarra/,
    descripcion:
      'Editor de diagramas de clases (Pizarra): crear clases con atributos y métodos, relaciones entre ' +
      'clases, exportar/importar (menú Archivo), comando de voz, digitalizar por foto. La generación de ' +
      'backend/frontend no está acá: se hace desde la tarjeta del proyecto en el Dashboard.',
    sugerencias: [
      '¿Cómo creo una relación de herencia?',
      '¿Cómo uso el comando de voz?',
      '¿Cómo exporto el diagrama a XMI?',
    ],
  },
]

const SUGERENCIAS_GENERALES = ['¿Qué puedo hacer con este sistema?']

export function contextoPantalla(pathname) {
  const pantalla = PANTALLAS.find((p) => p.patron.test(pathname))
  return pantalla?.descripcion ?? 'Pantalla no identificada.'
}

export function sugerenciasPantalla(pathname) {
  const pantalla = PANTALLAS.find((p) => p.patron.test(pathname))
  return pantalla?.sugerencias ?? SUGERENCIAS_GENERALES
}
