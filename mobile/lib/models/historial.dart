import 'dart:ui';

/// Entrada de GET /proyectos/{id}/historial (CU18).
class EntradaHistorial {
  final int id;
  final int autorId;
  final String autorNombre;
  final Color autorColor;
  final bool porAgente;
  final String? idElemento;
  final String? nombreElemento;
  final String resumen;

  /// Clases involucradas (para aplicar el filtro por clase a lo que llega en vivo).
  final List<String> idsClases;
  final DateTime createdAt;

  const EntradaHistorial({
    required this.id,
    required this.autorId,
    required this.autorNombre,
    required this.autorColor,
    required this.porAgente,
    required this.idElemento,
    required this.nombreElemento,
    required this.resumen,
    required this.idsClases,
    required this.createdAt,
  });

  /// Misma regla que el filtro del backend (GET /historial?usuario_id=&clase_id=).
  bool cumpleFiltros({int? usuarioId, String? claseId}) {
    if (usuarioId != null && autorId != usuarioId) return false;
    if (claseId != null && idElemento != claseId && !idsClases.contains(claseId)) return false;
    return true;
  }

  factory EntradaHistorial.fromJson(Map<String, dynamic> json) {
    return EntradaHistorial(
      id: json['id'] as int,
      autorId: json['autor_id'] as int,
      autorNombre: (json['autor_nombre'] as String?) ?? '',
      autorColor: colorDesdeHex(json['autor_color'] as String?),
      porAgente: (json['por_agente'] as bool?) ?? false,
      idElemento: json['id_elemento'] as String?,
      nombreElemento: json['nombre_elemento'] as String?,
      resumen: (json['resumen'] as String?) ?? '',
      idsClases: [for (final id in (json['ids_clases'] as List? ?? [])) id.toString()],
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

/// GET /proyectos/{id}/historial/filtros: quiénes y qué clases aparecen.
class FiltrosHistorial {
  final List<({int id, String nombre})> integrantes;
  final List<({String id, String nombre})> clases;

  const FiltrosHistorial({required this.integrantes, required this.clases});

  static const vacio = FiltrosHistorial(integrantes: [], clases: []);

  factory FiltrosHistorial.fromJson(Map<String, dynamic> json) {
    return FiltrosHistorial(
      integrantes: [
        for (final i in (json['integrantes'] as List? ?? []).cast<Map>())
          (id: i['id'] as int, nombre: i['nombre'] as String),
      ],
      clases: [
        for (final c in (json['clases'] as List? ?? []).cast<Map>())
          (id: c['id'] as String, nombre: c['nombre'] as String),
      ],
    );
  }
}

/// "#4c8dff" -> Color.
Color colorDesdeHex(String? hex) {
  final limpio = (hex ?? '').replaceFirst('#', '');
  final valor = int.tryParse(limpio, radix: 16);
  if (limpio.length != 6 || valor == null) return const Color(0xFF6B7280);
  return Color(0xFF000000 | valor);
}
