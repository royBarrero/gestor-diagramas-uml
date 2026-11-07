import 'dart:ui';

/// Mismos colores e iniciales que frontend/src/utils/avatar.js.
class ColorAvatar {
  final Color fondo;
  final Color texto;

  const ColorAvatar(this.fondo, this.texto);
}

const _coloresAvatar = [
  ColorAvatar(Color(0xFFE5574A), Color(0xFFFFFFFF)),
  ColorAvatar(Color(0xFF34D399), Color(0xFF04291B)),
  ColorAvatar(Color(0xFF1F7AE0), Color(0xFFFFFFFF)),
  ColorAvatar(Color(0xFFA78BFA), Color(0xFF1E1240)),
  ColorAvatar(Color(0xFFF5A524), Color(0xFF2B1A00)),
];

/// "Pepe González" -> "PG"; un solo nombre -> sus dos primeras letras.
String iniciales(String nombre) {
  final partes = nombre.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
  if (partes.isEmpty) return '?';
  if (partes.length == 1) {
    final p = partes.first;
    return (p.length >= 2 ? p.substring(0, 2) : p).toUpperCase();
  }
  return (partes[0][0] + partes[1][0]).toUpperCase();
}

/// Color estable por usuario, derivado de su id.
ColorAvatar colorAvatar(int id) => _coloresAvatar[id.abs() % _coloresAvatar.length];

/// Color de cada integrante en el chat y el historial (colorPorUsuario de la web).
const _paletaColaboradores = [
  Color(0xFF4C8DFF),
  Color(0xFFE0A030),
  Color(0xFF33B679),
  Color(0xFFE05C5C),
  Color(0xFFA06CE0),
  Color(0xFF3FBFBF),
];

Color colorPorUsuario(int id) => _paletaColaboradores[id.abs() % _paletaColaboradores.length];
