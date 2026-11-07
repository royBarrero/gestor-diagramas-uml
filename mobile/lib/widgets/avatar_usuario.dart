import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../utils/avatar.dart';

/// Círculo con las iniciales del usuario (igual a `.avatar` de la web).
class AvatarUsuario extends StatelessWidget {
  final int id;
  final String nombre;
  final double tamano;

  const AvatarUsuario({super.key, required this.id, required this.nombre, this.tamano = 32});

  @override
  Widget build(BuildContext context) {
    final color = colorAvatar(id);
    return Tooltip(
      message: nombre,
      child: _Circulo(tamano: tamano, fondo: color.fondo, texto: color.texto, etiqueta: iniciales(nombre)),
    );
  }
}

/// Círculo "+N" para los miembros que no entran.
class AvatarMas extends StatelessWidget {
  final int cantidad;

  const AvatarMas(this.cantidad, {super.key});

  @override
  Widget build(BuildContext context) {
    return _Circulo(tamano: 32, fondo: AppColors.borde, texto: AppColors.texto2, etiqueta: '+$cantidad');
  }
}

class _Circulo extends StatelessWidget {
  final double tamano;
  final Color fondo;
  final Color texto;
  final String etiqueta;

  const _Circulo({required this.tamano, required this.fondo, required this.texto, required this.etiqueta});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: tamano,
      height: tamano,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: fondo,
        shape: BoxShape.circle,
        border: Border.all(color: AppColors.tarjeta, width: 2),
      ),
      child: Text(
        etiqueta,
        style: TextStyle(color: texto, fontSize: tamano * 0.375, fontWeight: FontWeight.w700),
      ),
    );
  }
}
