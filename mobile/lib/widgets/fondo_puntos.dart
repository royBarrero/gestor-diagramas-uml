import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Fondo de puntos sutil, igual al panel de login de la web (AuthPanel).
class FondoPuntos extends StatelessWidget {
  final Widget child;

  const FondoPuntos({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _PuntosPainter(), child: child);
  }
}

class _PuntosPainter extends CustomPainter {
  static const _separacion = 22.0;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = AppColors.fondo);
    final punto = Paint()..color = Colors.white.withValues(alpha: 0.07);
    for (double y = 0; y < size.height; y += _separacion) {
      for (double x = 0; x < size.width; x += _separacion) {
        canvas.drawCircle(Offset(x, y), 1, punto);
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
