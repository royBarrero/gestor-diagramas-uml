/// Proyecto tal como lo devuelve GET /proyectos/mis-proyectos.
class Proyecto {
  final int id;
  final String nombre;
  final String? descripcion;
  final String rol; // "administrador" | "colaborador"
  final int totalClases;
  final int totalRelaciones;
  final DateTime? updatedAt;
  final List<MiembroResumen> miembros;

  const Proyecto({
    required this.id,
    required this.nombre,
    required this.descripcion,
    required this.rol,
    required this.totalClases,
    required this.totalRelaciones,
    required this.updatedAt,
    required this.miembros,
  });

  bool get esAdministrador => rol == 'administrador';

  factory Proyecto.fromJson(Map<String, dynamic> json) {
    final updatedAt = json['updated_at'] as String?;
    return Proyecto(
      id: json['id'] as int,
      nombre: json['nombre'] as String,
      descripcion: json['descripcion'] as String?,
      rol: json['rol'] as String,
      totalClases: (json['total_clases'] as int?) ?? 0,
      totalRelaciones: (json['total_relaciones'] as int?) ?? 0,
      updatedAt: updatedAt == null ? null : DateTime.parse(updatedAt),
      miembros: ((json['miembros'] as List?) ?? [])
          .map((m) => MiembroResumen.fromJson(m as Map<String, dynamic>))
          .toList(),
    );
  }
}

class MiembroResumen {
  final int id;
  final String nombre;

  const MiembroResumen({required this.id, required this.nombre});

  factory MiembroResumen.fromJson(Map<String, dynamic> json) {
    return MiembroResumen(id: json['id'] as int, nombre: json['nombre'] as String);
  }
}
