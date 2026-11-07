class Usuario {
  final int id;
  final String nombre;
  final String email;

  const Usuario({required this.id, required this.nombre, required this.email});

  factory Usuario.fromJson(Map<String, dynamic> json) {
    return Usuario(
      id: json['id'] as int,
      nombre: json['nombre'] as String,
      email: json['email'] as String,
    );
  }
}
