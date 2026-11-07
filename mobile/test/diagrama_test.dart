import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter_test/flutter_test.dart';

import 'package:gestor_diagramas_movil/models/diagrama.dart';
import 'package:gestor_diagramas_movil/widgets/diagrama/geometria_diagrama.dart';

void main() {
  test('Diagrama.fromJson lee el contenido de React Flow', () {
    final d = Diagrama.fromJson({
      'id': 1,
      'id_proyecto': 1,
      'nombre': 'Diagrama principal',
      'updated_at': '2026-11-01T10:00:00',
      'contenido': {
        'nodes': [
          {
            'id': 'a',
            'type': 'clase',
            'position': {'x': -460.5, 'y': 60.7},
            'measured': {'width': 240, 'height': 256},
            'data': {
              'nombre': 'Usuario',
              'atributos': [
                {'id': 'x', 'texto': 'id', 'tipo': '', 'visibilidad': 'privado'},
              ],
              'metodos': [],
            },
          },
          {'id': 'b', 'type': 'clase', 'position': {'x': 0, 'y': 0}, 'data': {'nombre': 'Rol'}},
        ],
        'edges': [
          {
            'id': 'r1',
            'source': 'a',
            'target': 'b',
            'data': {'tipo': 'herencia', 'nombre': null, 'multiplicidadOrigen': '1'},
          },
          // Apunta a una clase que no existe: se descarta.
          {'id': 'r2', 'source': 'a', 'target': 'zzz', 'data': {'tipo': 'asociacion'}},
        ],
      },
    });

    expect(d.clases.length, 2);
    expect(d.clases.first.atributos.first.simbolo, '-');
    expect(d.clases.first.atributos.first.tipo, isNull);
    expect(d.relaciones.length, 1);
    expect(d.relaciones.first.estiloLinea, 'recta');
    expect(d.relaciones.first.nombre, isNull);
  });

  test('la relación recta sale y llega por el borde de cada clase', () {
    const a = Rect.fromLTWH(0, 0, 240, 100);
    const b = Rect.fromLTWH(500, 0, 240, 100);
    final g = calcularRelacion(a, b, 'recta');
    expect(g.origen, const Offset(240, 50));
    expect(g.destino, const Offset(500, 50));
    expect(g.anguloOrigen, 0);
  });

  test('en curva/ortogonal se ancla al lado que mira a la otra clase', () {
    const a = Rect.fromLTWH(0, 0, 240, 100);
    const b = Rect.fromLTWH(0, 400, 240, 100);
    final g = calcularRelacion(a, b, 'ortogonal');
    expect(g.origen, const Offset(120, 100));
    expect(g.destino, const Offset(120, 400));
    expect(g.anguloOrigen, closeTo(math.pi / 2, 1e-9));
    expect(g.anguloDestino, closeTo(math.pi / 2, 1e-9));
  });
}
