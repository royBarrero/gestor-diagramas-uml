import 'package:flutter_test/flutter_test.dart';

import 'package:gestor_diagramas_movil/models/proyecto.dart';
import 'package:gestor_diagramas_movil/utils/avatar.dart';
import 'package:gestor_diagramas_movil/utils/fecha_relativa.dart';

void main() {
  test('iniciales igual que en la web', () {
    expect(iniciales('Pepe González'), 'PG');
    expect(iniciales('roy'), 'RO');
    expect(iniciales('  '), '?');
  });

  test('fechaRelativa', () {
    final ahora = DateTime.now();
    expect(fechaRelativa(null), 'Sin cambios todavía');
    expect(fechaRelativa(ahora.subtract(const Duration(seconds: 10))), 'Hace un momento');
    expect(fechaRelativa(ahora.subtract(const Duration(minutes: 12))), 'Hace 12 min');
    expect(fechaRelativa(ahora.subtract(const Duration(hours: 30))), 'Ayer');
    expect(fechaRelativa(ahora.subtract(const Duration(days: 3))), 'Hace 3 días');
  });

  test('Proyecto.fromJson lee la respuesta de /proyectos/mis-proyectos', () {
    final p = Proyecto.fromJson({
      'id': 7,
      'nombre': 'Tienda',
      'descripcion': null,
      'rol': 'colaborador',
      'total_miembros': 2,
      'total_clases': 3,
      'total_relaciones': 1,
      'updated_at': '2026-11-01T10:00:00',
      'miembros': [
        {'id': 1, 'nombre': 'Ana'},
        {'id': 2, 'nombre': 'Luis'},
      ],
      'backend_generado_en': null,
    });
    expect(p.esAdministrador, isFalse);
    expect(p.totalClases, 3);
    expect(p.miembros.length, 2);
    expect(p.updatedAt, isNotNull);
  });

  test('formatearHora usa la hora local aunque venga con zona horaria', () {
    final fecha = DateTime.parse('2026-11-07T10:26:56-04:00');
    final local = fecha.toLocal();
    String dos(int n) => n.toString().padLeft(2, '0');
    expect(formatearHora(fecha), endsWith('${dos(local.hour)}:${dos(local.minute)}'));
  });
}
