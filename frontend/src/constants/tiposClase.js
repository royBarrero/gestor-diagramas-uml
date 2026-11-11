// Clasificador UML de cada clase (`data.tipoClase`). Una clase sin el campo es
// 'clase' (diagramas guardados antes de que existiera). Espejo del backend:
// TIPOS_CLASE en backend/app/services/constantes_diagrama.py.
//
// `palabraClave` va antes del nombre (UML 2.5 permite «keyword» antes o arriba);
// `propiedad` va después del nombre ({abstract}, junto con el nombre en cursiva).
export const TIPOS_CLASE = [
  { valor: 'clase', etiqueta: 'Clase' },
  { valor: 'abstracta', etiqueta: 'Clase abstracta', propiedad: '{abstract}' },
  { valor: 'interfaz', etiqueta: 'Interfaz', palabraClave: '«interface»' },
  { valor: 'enumeracion', etiqueta: 'Enumeración', palabraClave: '«enumeration»' },
]

export function infoTipoClase(tipoClase) {
  return TIPOS_CLASE.find((t) => t.valor === tipoClase) ?? TIPOS_CLASE[0]
}
