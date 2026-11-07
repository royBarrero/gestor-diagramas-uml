import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../models/diagrama.dart';
import '../../theme/app_theme.dart';
import 'clase_widget.dart';
import 'geometria_diagrama.dart';
import 'relaciones_painter.dart';

/// Lienzo de solo lectura: se puede mover y hacer zoom (con los dedos o con
/// los botones), pero no editar.
class VisorDiagrama extends StatefulWidget {
  final Diagrama diagrama;

  const VisorDiagrama({super.key, required this.diagrama});

  @override
  State<VisorDiagrama> createState() => _VisorDiagramaState();
}

class _VisorDiagramaState extends State<VisorDiagrama> {
  static const _margen = 400.0;
  static const _escalaMin = 0.1;
  static const _escalaMax = 3.0;

  final _controller = TransformationController();
  late _Lienzo _lienzo;
  Size? _tamanoVista;

  @override
  void initState() {
    super.initState();
    _lienzo = _Lienzo.desde(widget.diagrama, _margen);
  }

  @override
  void didUpdateWidget(covariant VisorDiagrama oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.diagrama != widget.diagrama) {
      _lienzo = _Lienzo.desde(widget.diagrama, _margen);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  /// Encuadra todas las clases en la pantalla (como `fitView` de React Flow).
  void _ajustar() {
    final vista = _tamanoVista;
    if (vista == null) return;
    final contenido = _lienzo.contenido;
    const aire = 48.0;
    final escala = math
        .min((vista.width - aire) / contenido.width, (vista.height - aire) / contenido.height)
        .clamp(_escalaMin, 1.0);
    final dx = (vista.width - contenido.width * escala) / 2 - contenido.left * escala;
    final dy = (vista.height - contenido.height * escala) / 2 - contenido.top * escala;
    _controller.value = Matrix4.diagonal3Values(escala, escala, 1)..setTranslationRaw(dx, dy, 0);
  }

  void _zoom(double factor) {
    final vista = _tamanoVista;
    if (vista == null) return;
    final actual = _controller.value.getMaxScaleOnAxis();
    final nueva = (actual * factor).clamp(_escalaMin, _escalaMax);
    final f = nueva / actual;
    final cx = vista.width / 2;
    final cy = vista.height / 2;
    _controller.value = Matrix4.translationValues(cx, cy, 0)
        .multiplied(Matrix4.diagonal3Values(f, f, 1))
        .multiplied(Matrix4.translationValues(-cx, -cy, 0))
        .multiplied(_controller.value);
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final tamano = constraints.biggest;
        if (_tamanoVista != tamano) {
          final primeraVez = _tamanoVista == null;
          _tamanoVista = tamano;
          if (primeraVez) WidgetsBinding.instance.addPostFrameCallback((_) => _ajustar());
        }

        return Stack(
          children: [
            Positioned.fill(
              child: ColoredBox(
                color: AppColors.fondo,
                child: InteractiveViewer(
                  transformationController: _controller,
                  constrained: false,
                  boundaryMargin: const EdgeInsets.all(double.infinity),
                  minScale: _escalaMin,
                  maxScale: _escalaMax,
                  child: _lienzo.construir(),
                ),
              ),
            ),
            Positioned(
              right: 12,
              bottom: 12,
              child: _ControlesZoom(
                onAcercar: () => _zoom(1.25),
                onAlejar: () => _zoom(0.8),
                onAjustar: _ajustar,
              ),
            ),
          ],
        );
      },
    );
  }
}

/// Posiciones de todo en coordenadas del lienzo (ya desplazadas para que no
/// haya coordenadas negativas, que React Flow sí permite).
class _Lienzo {
  final Size tamano;
  final Rect contenido;
  final Map<String, Rect> rects;
  final List<ClaseUml> clases;
  final List<RelacionDibujable> relaciones;

  _Lienzo(this.tamano, this.contenido, this.rects, this.clases, this.relaciones);

  factory _Lienzo.desde(Diagrama diagrama, double margen) {
    final clases = diagrama.clases;
    double minX = 0, minY = 0, maxX = 0, maxY = 0;
    for (var i = 0; i < clases.length; i++) {
      final c = clases[i];
      final derecha = c.x + MedidasClase.ancho(c);
      final abajo = c.y + MedidasClase.alto(c);
      if (i == 0) {
        minX = c.x;
        minY = c.y;
        maxX = derecha;
        maxY = abajo;
      } else {
        minX = math.min(minX, c.x);
        minY = math.min(minY, c.y);
        maxX = math.max(maxX, derecha);
        maxY = math.max(maxY, abajo);
      }
    }

    final desplazamiento = Offset(margen - minX, margen - minY);
    final rects = {
      for (final c in clases)
        c.id: Rect.fromLTWH(
          c.x + desplazamiento.dx,
          c.y + desplazamiento.dy,
          MedidasClase.ancho(c),
          MedidasClase.alto(c),
        ),
    };

    final relaciones = [
      for (final r in diagrama.relaciones)
        RelacionDibujable(
          r,
          calcularRelacion(rects[r.origen]!, rects[r.destino]!, r.estiloLinea),
          r.claseAsociacion == null ? null : rects[r.claseAsociacion],
        ),
    ];

    final contenido = Rect.fromLTRB(
      minX + desplazamiento.dx,
      minY + desplazamiento.dy,
      maxX + desplazamiento.dx,
      maxY + desplazamiento.dy,
    );
    final tamano = Size(contenido.right + margen, contenido.bottom + margen);
    return _Lienzo(tamano, contenido, rects, clases, relaciones);
  }

  Widget construir() {
    return SizedBox.fromSize(
      size: tamano,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned.fill(child: CustomPaint(painter: RelacionesPainter(relaciones))),
          for (final c in clases)
            Positioned(left: rects[c.id]!.left, top: rects[c.id]!.top, child: ClaseWidget(clase: c)),
          // Etiquetas por encima de las clases, como el EdgeLabelRenderer web.
          for (final r in relaciones) ..._etiquetas(r),
        ],
      ),
    );
  }

  List<Widget> _etiquetas(RelacionDibujable r) {
    final g = r.geometria;
    return [
      if (r.relacion.multiplicidadOrigen != null)
        _centrado(g.etiquetaOrigen, _EtiquetaMultiplicidad(r.relacion.multiplicidadOrigen!)),
      if (r.relacion.multiplicidadDestino != null)
        _centrado(g.etiquetaDestino, _EtiquetaMultiplicidad(r.relacion.multiplicidadDestino!)),
      if (r.relacion.nombre != null) _centrado(g.puntoMedio, _EtiquetaNombre(r.relacion.nombre!)),
    ];
  }

  Widget _centrado(Offset punto, Widget hijo) {
    return Positioned(
      left: punto.dx,
      top: punto.dy,
      child: FractionalTranslation(translation: const Offset(-0.5, -0.5), child: hijo),
    );
  }
}

class _EtiquetaMultiplicidad extends StatelessWidget {
  final String texto;

  const _EtiquetaMultiplicidad(this.texto);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: AppColors.barra,
        border: Border.all(color: AppColors.bordeEtiqueta),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(texto, style: GoogleFonts.jetBrainsMono(fontSize: 11, color: AppColors.texto2)),
    );
  }
}

class _EtiquetaNombre extends StatelessWidget {
  final String texto;

  const _EtiquetaNombre(this.texto);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.tarjeta,
        border: Border.all(color: AppColors.borde),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        texto,
        style: const TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w500,
          fontStyle: FontStyle.italic,
          color: AppColors.texto,
        ),
      ),
    );
  }
}

class _ControlesZoom extends StatelessWidget {
  final VoidCallback onAcercar;
  final VoidCallback onAlejar;
  final VoidCallback onAjustar;

  const _ControlesZoom({required this.onAcercar, required this.onAlejar, required this.onAjustar});

  @override
  Widget build(BuildContext context) {
    Widget boton(IconData icono, String tooltip, VoidCallback onTap) => IconButton(
          tooltip: tooltip,
          onPressed: onTap,
          icon: Icon(icono, size: 20, color: AppColors.texto2),
        );

    return Container(
      decoration: BoxDecoration(
        color: AppColors.tarjeta,
        border: Border.all(color: AppColors.borde),
        borderRadius: BorderRadius.circular(10),
        boxShadow: const [BoxShadow(color: Color(0x66000000), blurRadius: 20, offset: Offset(0, 6))],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          boton(Icons.add, 'Acercar', onAcercar),
          boton(Icons.remove, 'Alejar', onAlejar),
          boton(Icons.fit_screen_outlined, 'Ajustar a la pantalla', onAjustar),
        ],
      ),
    );
  }
}
