/// Mensaje de GET /proyectos/{id}/mensajes (chat grupal, CU15–CU17).
class Mensaje {
  final int id;
  final String tipo; // usuario | agente | sistema
  final String texto;
  final int? autorId;
  final String? autorNombre;
  final int? destinoId;
  final String? destinoNombre;
  final AccionAgente? accion;
  final bool sugerenciaResuelta;
  final DateTime createdAt;

  const Mensaje({
    required this.id,
    required this.tipo,
    required this.texto,
    required this.autorId,
    required this.autorNombre,
    required this.destinoId,
    required this.destinoNombre,
    required this.accion,
    required this.sugerenciaResuelta,
    required this.createdAt,
  });

  factory Mensaje.fromJson(Map<String, dynamic> json) {
    final accion = json['accion'] as Map?;
    return Mensaje(
      id: json['id'] as int,
      tipo: json['tipo'] as String,
      texto: (json['texto'] as String?) ?? '',
      autorId: json['autor_id'] as int?,
      autorNombre: json['autor_nombre'] as String?,
      destinoId: json['destino_id'] as int?,
      destinoNombre: json['destino_nombre'] as String?,
      accion: accion == null ? null : AccionAgente.fromJson(accion.cast<String, dynamic>()),
      sugerenciaResuelta: (json['sugerencia_resuelta'] as bool?) ?? false,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

/// Cambio propuesto por el agente (CU17). En el móvil solo se muestra su estado.
class AccionAgente {
  final int id;
  final String estado; // pendiente | confirmada | cancelada | aplicada | deshecha
  final int idSolicitante;

  const AccionAgente({required this.id, required this.estado, required this.idSolicitante});

  factory AccionAgente.fromJson(Map<String, dynamic> json) {
    return AccionAgente(
      id: json['id'] as int,
      estado: json['estado'] as String,
      idSolicitante: json['id_solicitante'] as int,
    );
  }
}
