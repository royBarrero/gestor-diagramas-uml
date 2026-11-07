import 'dart:math' as math;

import 'package:flutter/rendering.dart';

import '../../models/diagrama.dart';
import '../../theme/app_theme.dart';
import 'geometria_diagrama.dart';

const _largoForma = 16.0;
const _anchoForma = 10.0;
const _largoFlecha = 12.0;
const _anchoFlecha = 8.0;
const _colorLinea = AppColors.texto3;

/// Relación ya resuelta: geometría + datos + (opcional) la clase de asociación.
class RelacionDibujable {
  final RelacionUml relacion;
  final GeometriaRelacion geometria;
  final Rect? claseAsociacion;

  const RelacionDibujable(this.relacion, this.geometria, this.claseAsociacion);
}

/// Dibuja la cuadrícula del lienzo y las relaciones, con los mismos
/// extremos UML que RelacionEdge.jsx (triángulo, rombos, flecha abierta).
class RelacionesPainter extends CustomPainter {
  final List<RelacionDibujable> relaciones;

  RelacionesPainter(this.relaciones);

  @override
  void paint(Canvas canvas, Size size) {
    _cuadricula(canvas, size);

    final trazo = Paint()
      ..color = _colorLinea
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    final relleno = Paint()..style = PaintingStyle.fill;

    for (final r in relaciones) {
      final g = r.geometria;
      final tipo = r.relacion.tipo;

      if (tipo == 'dependencia') {
        canvas.drawPath(_punteado(g.trazo), trazo);
      } else {
        canvas.drawPath(g.trazo, trazo);
      }

      if (r.claseAsociacion != null) {
        final borde = interseccionConBorde(r.claseAsociacion!, g.puntoMedio);
        final linea = Path()
          ..moveTo(g.puntoMedio.dx, g.puntoMedio.dy)
          ..lineTo(borde.dx, borde.dy);
        canvas.drawPath(_punteado(linea), trazo);
      }

      switch (tipo) {
        case 'dependencia':
          canvas.drawPath(_flecha(g.destino, g.anguloDestino), trazo);
        case 'herencia':
          final forma = _triangulo(g.destino, g.anguloDestino);
          canvas.drawPath(forma, relleno..color = AppColors.fondo);
          canvas.drawPath(forma, trazo);
        case 'agregacion':
          final forma = _rombo(g.origen, g.anguloOrigen);
          canvas.drawPath(forma, relleno..color = AppColors.fondo);
          canvas.drawPath(forma, trazo);
        case 'composicion':
          final forma = _rombo(g.origen, g.anguloOrigen);
          canvas.drawPath(forma, relleno..color = _colorLinea);
          canvas.drawPath(forma, trazo);
      }
    }
  }

  /// Cuadrícula de dos niveles como la pizarra web: cada 24px y guías cada 120px.
  void _cuadricula(Canvas canvas, Size size) {
    final fina = Paint()
      ..color = const Color(0x09FFFFFF)
      ..strokeWidth = 1;
    final guia = Paint()
      ..color = const Color(0x12FFFFFF)
      ..strokeWidth = 1;
    for (double x = 0; x <= size.width; x += 24) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), x % 120 == 0 ? guia : fina);
    }
    for (double y = 0; y <= size.height; y += 24) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), y % 120 == 0 ? guia : fina);
    }
  }

  Path _punteado(Path original) {
    final resultado = Path();
    for (final metrica in original.computeMetrics()) {
      double d = 0;
      while (d < metrica.length) {
        resultado.addPath(metrica.extractPath(d, math.min(d + 6, metrica.length)), Offset.zero);
        d += 10; // 6 de trazo + 4 de espacio
      }
    }
    return resultado;
  }

  Offset _dir(double angulo) => Offset(math.cos(angulo), math.sin(angulo));
  Offset _perp(double angulo) => Offset(-math.sin(angulo), math.cos(angulo));

  Path _triangulo(Offset punta, double angulo) {
    final base = punta - _dir(angulo) * _largoForma;
    final p = _perp(angulo) * (_anchoForma / 2);
    return Path()
      ..moveTo(punta.dx, punta.dy)
      ..lineTo((base + p).dx, (base + p).dy)
      ..lineTo((base - p).dx, (base - p).dy)
      ..close();
  }

  Path _rombo(Offset punta, double angulo) {
    final medio = punta + _dir(angulo) * (_largoForma / 2);
    final fin = punta + _dir(angulo) * _largoForma;
    final p = _perp(angulo) * (_anchoForma / 2);
    return Path()
      ..moveTo(punta.dx, punta.dy)
      ..lineTo((medio + p).dx, (medio + p).dy)
      ..lineTo(fin.dx, fin.dy)
      ..lineTo((medio - p).dx, (medio - p).dy)
      ..close();
  }

  Path _flecha(Offset punta, double angulo) {
    final base = punta - _dir(angulo) * _largoFlecha;
    final p = _perp(angulo) * (_anchoFlecha / 2);
    return Path()
      ..moveTo((base + p).dx, (base + p).dy)
      ..lineTo(punta.dx, punta.dy)
      ..lineTo((base - p).dx, (base - p).dy);
  }

  @override
  bool shouldRepaint(covariant RelacionesPainter oldDelegate) =>
      oldDelegate.relaciones != relaciones;
}
