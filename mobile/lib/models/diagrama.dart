/// Diagrama tal como lo devuelve GET /diagramas/proyecto/{id}. El `contenido`
/// es el JSON de React Flow: `nodes` (clases) y `edges` (relaciones).
class Diagrama {
  final int id;
  final List<ClaseUml> clases;
  final List<RelacionUml> relaciones;
  final DateTime? updatedAt;

  const Diagrama({
    required this.id,
    required this.clases,
    required this.relaciones,
    required this.updatedAt,
  });

  factory Diagrama.fromJson(Map<String, dynamic> json) {
    final contenido = (json['contenido'] as Map?) ?? {};
    final clases = ((contenido['nodes'] as List?) ?? [])
        .whereType<Map>()
        .where((n) => n['type'] == null || n['type'] == 'clase')
        .map((n) => ClaseUml.fromJson(n.cast<String, dynamic>()))
        .toList();
    final ids = {for (final c in clases) c.id};
    // Una relación hacia una clase que ya no existe no se puede dibujar.
    final relaciones = ((contenido['edges'] as List?) ?? [])
        .whereType<Map>()
        .map((e) => RelacionUml.fromJson(e.cast<String, dynamic>()))
        .where((r) => ids.contains(r.origen) && ids.contains(r.destino))
        .toList();
    final updatedAt = json['updated_at'] as String?;

    return Diagrama(
      id: json['id'] as int,
      clases: clases,
      relaciones: relaciones,
      updatedAt: updatedAt == null ? null : DateTime.parse(updatedAt),
    );
  }
}

class ClaseUml {
  final String id;
  final String nombre;
  final double x;
  final double y;

  /// Ancho medido en la web (si existe), para respetar la separación entre clases.
  final double? anchoWeb;
  final List<MiembroClase> atributos;
  final List<MiembroClase> metodos;

  const ClaseUml({
    required this.id,
    required this.nombre,
    required this.x,
    required this.y,
    required this.anchoWeb,
    required this.atributos,
    required this.metodos,
  });

  factory ClaseUml.fromJson(Map<String, dynamic> json) {
    final data = (json['data'] as Map?)?.cast<String, dynamic>() ?? {};
    final posicion = (json['position'] as Map?) ?? {};
    final medido = (json['measured'] as Map?) ?? {};

    List<MiembroClase> lista(String clave) => ((data[clave] as List?) ?? [])
        .whereType<Map>()
        .map((m) => MiembroClase.fromJson(m.cast<String, dynamic>()))
        .toList();

    return ClaseUml(
      id: json['id'].toString(),
      nombre: (data['nombre'] as String?) ?? 'Clase',
      x: (posicion['x'] as num?)?.toDouble() ?? 0,
      y: (posicion['y'] as num?)?.toDouble() ?? 0,
      anchoWeb: (medido['width'] as num?)?.toDouble(),
      atributos: lista('atributos'),
      metodos: lista('metodos'),
    );
  }
}

/// Atributo o método de una clase.
class MiembroClase {
  final String texto;
  final String? tipo;
  final String visibilidad; // publico | privado | protegido

  const MiembroClase({required this.texto, required this.tipo, required this.visibilidad});

  String get simbolo => switch (visibilidad) {
        'privado' => '-',
        'protegido' => '#',
        _ => '+',
      };

  factory MiembroClase.fromJson(Map<String, dynamic> json) {
    final tipo = (json['tipo'] as String?)?.trim();
    return MiembroClase(
      texto: (json['texto'] as String?) ?? '',
      tipo: (tipo == null || tipo.isEmpty) ? null : tipo,
      visibilidad: (json['visibilidad'] as String?) ?? 'publico',
    );
  }
}

class RelacionUml {
  final String id;
  final String origen;
  final String destino;
  final String tipo; // asociacion | herencia | agregacion | composicion | dependencia
  final String? nombre;
  final String estiloLinea; // recta | curva | ortogonal
  final String? multiplicidadOrigen;
  final String? multiplicidadDestino;

  /// Clase de asociación (UML), si tiene.
  final String? claseAsociacion;

  const RelacionUml({
    required this.id,
    required this.origen,
    required this.destino,
    required this.tipo,
    required this.nombre,
    required this.estiloLinea,
    required this.multiplicidadOrigen,
    required this.multiplicidadDestino,
    required this.claseAsociacion,
  });

  factory RelacionUml.fromJson(Map<String, dynamic> json) {
    final data = (json['data'] as Map?)?.cast<String, dynamic>() ?? {};
    String? texto(String clave) {
      final valor = (data[clave] as String?)?.trim();
      return (valor == null || valor.isEmpty) ? null : valor;
    }

    return RelacionUml(
      id: json['id'].toString(),
      origen: json['source'].toString(),
      destino: json['target'].toString(),
      tipo: texto('tipo') ?? 'asociacion',
      nombre: texto('nombre'),
      estiloLinea: texto('estiloLinea') ?? 'recta',
      multiplicidadOrigen: texto('multiplicidadOrigen'),
      multiplicidadDestino: texto('multiplicidadDestino'),
      claseAsociacion: texto('claseAsociacion'),
    );
  }
}
