import 'package:flutter_test/flutter_test.dart';

import 'package:gestor_diagramas_movil/models/usuario.dart';

void main() {
  test('Usuario.fromJson lee la respuesta de /auth/me', () {
    final usuario = Usuario.fromJson({
      'id': 1,
      'nombre': 'Ana',
      'email': 'ana@correo.com',
      'created_at': '2026-01-01T00:00:00',
    });

    expect(usuario.id, 1);
    expect(usuario.nombre, 'Ana');
    expect(usuario.email, 'ana@correo.com');
  });
}
