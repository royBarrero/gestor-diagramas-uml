import 'package:flutter/painting.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:gestor_diagramas_movil/models/historial.dart';
import 'package:gestor_diagramas_movil/models/mensaje.dart';
import 'package:gestor_diagramas_movil/widgets/mensaje_formateado.dart';

void main() {
  test('EntradaHistorial.fromJson lee /historial', () {
    final e = EntradaHistorial.fromJson({
      'id': 3,
      'id_proyecto': 1,
      'autor_id': 2,
      'autor_nombre': 'Ana',
      'autor_color': '#e0a030',
      'por_agente': true,
      'origen': 'agente',
      'tipo_operacion': 'crear_clase',
      'id_elemento': 'clase-1',
      'nombre_elemento': 'Usuario',
      'resumen': 'creó la clase Usuario',
      'ids_clases': ['clase-1'],
      'created_at': '2026-11-07T10:00:00',
    });
    expect(e.porAgente, isTrue);
    expect(e.autorColor, const Color(0xFFE0A030));
  });

  test('Mensaje.fromJson lee una sugerencia del agente con su acción', () {
    final m = Mensaje.fromJson({
      'id': 9,
      'id_proyecto': 1,
      'tipo': 'agente',
      'texto': 'Hola',
      'autor_id': null,
      'destino_id': 2,
      'destino_nombre': 'Ana',
      'elemento_referenciado': 'clase-1',
      'accion': {'id': 4, 'estado': 'pendiente', 'id_solicitante': 2},
      'sugerencia_resuelta': false,
      'created_at': '2026-11-07T10:00:00',
    });
    expect(m.accion!.estado, 'pendiente');
    expect(m.autorId, isNull);
  });

  test('parsearBloques agrupa como MensajeFormateado.jsx', () {
    final bloques = parsearBloques('# Revisión\nTexto uno\nsigue\n\n1. Primero\n   continúa\n2. Segundo\n- a\n- b');
    expect(bloques.map((b) => b.tipo).toList(), ['titulo', 'parrafo', 'numerada', 'vinetas']);
    expect(bloques[1].items.first, 'Texto uno sigue');
    expect(bloques[2].items, ['Primero continúa', 'Segundo']);
    expect(bloques[3].items, ['a', 'b']);
  });

  test('una entrada en vivo respeta los filtros del historial', () {
    final e = EntradaHistorial.fromJson({
      'id': 1,
      'autor_id': 2,
      'autor_nombre': 'Ana',
      'autor_color': '#4c8dff',
      'por_agente': false,
      'id_elemento': 'clase-a',
      'resumen': 'creó una relación',
      'ids_clases': ['clase-a', 'clase-b'],
      'created_at': '2026-11-07T10:00:00-04:00',
    });
    expect(e.cumpleFiltros(), isTrue);
    expect(e.cumpleFiltros(usuarioId: 2, claseId: 'clase-b'), isTrue);
    expect(e.cumpleFiltros(usuarioId: 3), isFalse);
    expect(e.cumpleFiltros(claseId: 'clase-z'), isFalse);
  });
}
