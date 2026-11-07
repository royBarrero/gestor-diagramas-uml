import 'dart:math' as math;
import 'dart:ui';

import '../../models/diagrama.dart';

/// Medidas fijas de una clase. El widget [ClaseWidget] respeta exactamente
/// estas medidas para que las relaciones se dibujen pegadas a los bordes.
class MedidasClase {
  static const anchoMinimo = 240.0;
  static const borde = 1.5;
  static const altoHeader = 50.0;
  static const altoFila = 28.0;
  static const espacioFilas = 2.0;
  static const paddingSeccionArriba = 8.0;
  static const paddingSeccionAbajo = 6.0;

  static double ancho(ClaseUml clase) => math.max(anchoMinimo, clase.anchoWeb ?? 0);

  static double altoSeccion(int filas) {
    final contenido = filas == 0 ? 0.0 : filas * altoFila + (filas - 1) * espacioFilas;
    return paddingSeccionArriba + contenido + paddingSeccionAbajo;
  }

  static double alto(ClaseUml clase) {
    return borde * 2 +
        altoHeader +
        1 + // línea bajo el header
        altoSeccion(clase.atributos.length) +
        1 + // separador atributos / métodos
        altoSeccion(clase.metodos.length);
  }
}

enum Lado { arriba, derecha, abajo, izquierda }

/// Geometría ya calculada de una relación, en coordenadas del lienzo.
class GeometriaRelacion {
  final Path trazo;
  final Offset origen;
  final Offset destino;

  /// Dirección (radianes) con la que la línea sale del origen.
  final double anguloOrigen;

  /// Dirección (radianes) con la que la línea llega al destino.
  final double anguloDestino;
  final Offset puntoMedio;

  const GeometriaRelacion({
    required this.trazo,
    required this.origen,
    required this.destino,
    required this.anguloOrigen,
    required this.anguloDestino,
    required this.puntoMedio,
  });

  /// Dónde va la etiqueta de multiplicidad de cada extremo (a ~30px del borde).
  Offset get etiquetaOrigen {
    final d = _desplazamiento;
    return origen + Offset(math.cos(anguloOrigen), math.sin(anguloOrigen)) * d;
  }

  Offset get etiquetaDestino {
    final d = _desplazamiento;
    return destino - Offset(math.cos(anguloDestino), math.sin(anguloDestino)) * d;
  }

  double get _desplazamiento {
    final distancia = (destino - origen).distance;
    return math.max(0, math.min(30, distancia / 2 - 10));
  }
}

/// Mismo algoritmo de "floating edges" que RelacionEdge.jsx: punto donde la
/// línea centro-a-centro cruza el borde del rectángulo.
Offset interseccionConBorde(Rect borde, Offset objetivo) {
  final w = borde.width / 2;
  final h = borde.height / 2;
  final x2 = borde.center.dx;
  final y2 = borde.center.dy;
  final x1 = objetivo.dx;
  final y1 = objetivo.dy;

  final xx1 = (x1 - x2) / (2 * w) - (y1 - y2) / (2 * h);
  final yy1 = (x1 - x2) / (2 * w) + (y1 - y2) / (2 * h);
  final suma = xx1.abs() + yy1.abs();
  final a = 1 / (suma == 0 ? 1 : suma);
  final xx3 = a * xx1;
  final yy3 = a * yy1;

  return Offset(w * (xx3 + yy3) + x2, h * (-xx3 + yy3) + y2);
}

/// Lado del rectángulo que mira hacia el otro (para curva / en L).
({Offset punto, Lado lado}) anclaCardinal(Rect borde, Rect objetivo) {
  final dx = objetivo.center.dx - borde.center.dx;
  final dy = objetivo.center.dy - borde.center.dy;
  if (dx.abs() > dy.abs()) {
    return dx > 0
        ? (punto: Offset(borde.right, borde.center.dy), lado: Lado.derecha)
        : (punto: Offset(borde.left, borde.center.dy), lado: Lado.izquierda);
  }
  return dy > 0
      ? (punto: Offset(borde.center.dx, borde.bottom), lado: Lado.abajo)
      : (punto: Offset(borde.center.dx, borde.top), lado: Lado.arriba);
}

double anguloSalida(Lado lado) => switch (lado) {
      Lado.derecha => 0,
      Lado.abajo => math.pi / 2,
      Lado.izquierda => math.pi,
      Lado.arriba => -math.pi / 2,
    };

bool _esHorizontal(Lado lado) => lado == Lado.derecha || lado == Lado.izquierda;

/// Igual a la curvatura de getBezierPath de React Flow (curvature 0.25).
double _offsetControl(double distancia) =>
    distancia >= 0 ? 0.5 * distancia : 0.25 * 25 * math.sqrt(-distancia);

Offset _puntoControl(Offset p, Lado lado, Offset otro) => switch (lado) {
      Lado.derecha => Offset(p.dx + _offsetControl(otro.dx - p.dx), p.dy),
      Lado.izquierda => Offset(p.dx - _offsetControl(p.dx - otro.dx), p.dy),
      Lado.abajo => Offset(p.dx, p.dy + _offsetControl(otro.dy - p.dy)),
      Lado.arriba => Offset(p.dx, p.dy - _offsetControl(p.dy - otro.dy)),
    };

GeometriaRelacion calcularRelacion(Rect origen, Rect destino, String estiloLinea) {
  if (estiloLinea != 'curva' && estiloLinea != 'ortogonal') {
    final s = interseccionConBorde(origen, destino.center);
    final t = interseccionConBorde(destino, origen.center);
    final angulo = math.atan2(t.dy - s.dy, t.dx - s.dx);
    return GeometriaRelacion(
      trazo: Path()
        ..moveTo(s.dx, s.dy)
        ..lineTo(t.dx, t.dy),
      origen: s,
      destino: t,
      anguloOrigen: angulo,
      anguloDestino: angulo,
      puntoMedio: (s + t) / 2,
    );
  }

  final a = anclaCardinal(origen, destino);
  final b = anclaCardinal(destino, origen);
  final s = a.punto;
  final t = b.punto;
  final anguloOrigen = anguloSalida(a.lado);
  final anguloDestino = anguloSalida(b.lado) + math.pi; // llega "hacia adentro"

  if (estiloLinea == 'curva') {
    final c1 = _puntoControl(s, a.lado, t);
    final c2 = _puntoControl(t, b.lado, s);
    final medio = s * 0.125 + c1 * 0.375 + c2 * 0.375 + t * 0.125;
    return GeometriaRelacion(
      trazo: Path()
        ..moveTo(s.dx, s.dy)
        ..cubicTo(c1.dx, c1.dy, c2.dx, c2.dy, t.dx, t.dy),
      origen: s,
      destino: t,
      anguloOrigen: anguloOrigen,
      anguloDestino: anguloDestino,
      puntoMedio: medio,
    );
  }

  // Ortogonal ("En L"): tramos horizontales/verticales.
  final puntos = <Offset>[s];
  final hS = _esHorizontal(a.lado);
  final hT = _esHorizontal(b.lado);
  if (hS && hT) {
    final mx = (s.dx + t.dx) / 2;
    puntos.addAll([Offset(mx, s.dy), Offset(mx, t.dy)]);
  } else if (!hS && !hT) {
    final my = (s.dy + t.dy) / 2;
    puntos.addAll([Offset(s.dx, my), Offset(t.dx, my)]);
  } else if (hS) {
    puntos.add(Offset(t.dx, s.dy));
  } else {
    puntos.add(Offset(s.dx, t.dy));
  }
  puntos.add(t);

  final trazo = Path()..moveTo(s.dx, s.dy);
  for (final p in puntos.skip(1)) {
    trazo.lineTo(p.dx, p.dy);
  }
  return GeometriaRelacion(
    trazo: trazo,
    origen: s,
    destino: t,
    anguloOrigen: anguloOrigen,
    anguloDestino: anguloDestino,
    puntoMedio: (s + t) / 2,
  );
}
