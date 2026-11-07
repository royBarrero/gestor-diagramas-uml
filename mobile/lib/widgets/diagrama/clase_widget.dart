import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../models/diagrama.dart';
import '../../theme/app_theme.dart';
import 'geometria_diagrama.dart';

/// Clase UML en solo lectura, con el mismo aspecto que ClaseNode.jsx.
/// Su tamaño es exactamente el de [MedidasClase].
class ClaseWidget extends StatelessWidget {
  final ClaseUml clase;

  const ClaseWidget({super.key, required this.clase});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: MedidasClase.ancho(clase),
      height: MedidasClase.alto(clase),
      decoration: BoxDecoration(
        color: AppColors.tarjeta,
        border: Border.all(color: AppColors.borde, width: MedidasClase.borde),
        borderRadius: BorderRadius.circular(12),
        boxShadow: const [
          BoxShadow(color: Color(0x59000000), blurRadius: 24, offset: Offset(0, 8)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Header(nombre: clase.nombre),
          const _Linea(),
          _Seccion(items: clase.atributos),
          const _Linea(),
          _Seccion(items: clase.metodos),
        ],
      ),
    );
  }
}

class _Linea extends StatelessWidget {
  const _Linea();

  @override
  Widget build(BuildContext context) => const SizedBox(
        height: 1,
        child: ColoredBox(color: AppColors.borde),
      );
}

class _Header extends StatelessWidget {
  final String nombre;

  const _Header({required this.nombre});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: MedidasClase.altoHeader,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 6, 14, 2),
        child: Row(
          children: [
            Container(
              width: 9,
              height: 9,
              decoration: const BoxDecoration(color: Color(0xFF6B7280), shape: BoxShape.circle),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                nombre,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.texto),
              ),
            ),
            const SizedBox(width: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
              decoration: BoxDecoration(
                color: AppColors.estereotipoBg,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                'ENTITY',
                style: GoogleFonts.jetBrainsMono(
                    fontSize: 10, letterSpacing: 0.8, color: AppColors.texto3),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Seccion extends StatelessWidget {
  final List<MiembroClase> items;

  const _Seccion({required this.items});

  @override
  Widget build(BuildContext context) {
    final mono = GoogleFonts.jetBrainsMono(fontSize: 13, color: AppColors.texto);
    return SizedBox(
      height: MedidasClase.altoSeccion(items.length),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
            16, MedidasClase.paddingSeccionArriba, 16, MedidasClase.paddingSeccionAbajo),
        child: Column(
          children: [
            for (var i = 0; i < items.length; i++) ...[
              if (i > 0) const SizedBox(height: MedidasClase.espacioFilas),
              SizedBox(
                height: MedidasClase.altoFila,
                child: Row(
                  children: [
                    Text(items[i].simbolo, style: mono.copyWith(color: AppColors.primario)),
                    const SizedBox(width: 6),
                    Flexible(
                      child: Text(
                        items[i].texto,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: mono,
                      ),
                    ),
                    if (items[i].tipo != null) ...[
                      const SizedBox(width: 8),
                      Text(': ', style: mono.copyWith(color: AppColors.texto3)),
                      Text(items[i].tipo!, style: mono.copyWith(color: AppColors.tipo)),
                    ],
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
