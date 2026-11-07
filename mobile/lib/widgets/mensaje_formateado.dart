import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../theme/app_theme.dart';

/// Markdown mínimo para las respuestas del agente, igual que
/// frontend/src/components/Asistente/MensajeFormateado.jsx: párrafos,
/// títulos (#), listas numeradas, viñetas, **negrita** y `código`.
class MensajeFormateado extends StatelessWidget {
  final String texto;

  const MensajeFormateado(this.texto, {super.key});

  static final _numerada = RegExp(r'^\s*(\d+)[.)]\s+(.*)$');
  static final _vineta = RegExp(r'^\s*[-*•]\s+(.*)$');
  static final _titulo = RegExp(r'^\s*#{1,6}\s+(.*)$');
  static final _enLinea = RegExp(r'(\*\*[^*]+\*\*|`[^`]+`)');

  static const _base = TextStyle(fontSize: 15, height: 1.65, color: AppColors.texto);

  @override
  Widget build(BuildContext context) {
    final bloques = parsearBloques(texto);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < bloques.length; i++) ...[
          if (i > 0) const SizedBox(height: 12),
          _bloque(bloques[i]),
        ],
      ],
    );
  }

  Widget _bloque(BloqueMarkdown b) {
    switch (b.tipo) {
      case 'titulo':
        return Text.rich(_enLineaSpan(b.items.first),
            style: AppTheme.heading(size: 15).copyWith(height: 1.5));
      case 'numerada':
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (var i = 0; i < b.items.length; i++)
              Padding(
                padding: EdgeInsets.only(top: i == 0 ? 0 : 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 24,
                      height: 24,
                      margin: const EdgeInsets.only(top: 1),
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: AppColors.primario.withValues(alpha: 0.16),
                        shape: BoxShape.circle,
                      ),
                      child: Text('${b.inicio + i}',
                          style: const TextStyle(
                              fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.primario)),
                    ),
                    const SizedBox(width: 12),
                    Expanded(child: Text.rich(_enLineaSpan(b.items[i]), style: _base)),
                  ],
                ),
              ),
          ],
        );
      case 'vinetas':
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (var i = 0; i < b.items.length; i++)
              Padding(
                padding: EdgeInsets.only(top: i == 0 ? 0 : 6, left: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('•  ', style: TextStyle(fontSize: 15, height: 1.65, color: AppColors.primario)),
                    Expanded(child: Text.rich(_enLineaSpan(b.items[i]), style: _base)),
                  ],
                ),
              ),
          ],
        );
      default:
        return Text.rich(_enLineaSpan(b.items.first), style: _base);
    }
  }

  TextSpan _enLineaSpan(String texto) {
    final spans = <InlineSpan>[];
    texto.splitMapJoin(
      _enLinea,
      onMatch: (m) {
        final parte = m[0]!;
        if (parte.startsWith('**')) {
          spans.add(TextSpan(
            text: parte.substring(2, parte.length - 2),
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
          ));
        } else {
          spans.add(TextSpan(
            text: ' ${parte.substring(1, parte.length - 1)} ',
            style: GoogleFonts.jetBrainsMono(
              fontSize: 13,
              color: AppColors.primario,
              backgroundColor: AppColors.fondo,
            ),
          ));
        }
        return '';
      },
      onNonMatch: (s) {
        if (s.isNotEmpty) spans.add(TextSpan(text: s));
        return '';
      },
    );
    return TextSpan(children: spans);
  }
}

class BloqueMarkdown {
  final String tipo; // parrafo | titulo | numerada | vinetas
  final List<String> items;
  final int inicio;

  BloqueMarkdown(this.tipo, this.items, {this.inicio = 1});
}

/// Agrupa las líneas en bloques (misma lógica que parsearBloques de la web).
List<BloqueMarkdown> parsearBloques(String texto) {
  final bloques = <BloqueMarkdown>[];
  var parrafo = <String>[];

  void cerrarParrafo() {
    if (parrafo.isNotEmpty) {
      bloques.add(BloqueMarkdown('parrafo', [parrafo.join(' ')]));
      parrafo = [];
    }
  }

  for (final linea in texto.replaceAll('\r\n', '\n').split('\n')) {
    final numerada = MensajeFormateado._numerada.firstMatch(linea);
    final vineta = MensajeFormateado._vineta.firstMatch(linea);
    final titulo = MensajeFormateado._titulo.firstMatch(linea);
    final ultimo = bloques.isEmpty ? null : bloques.last;

    if (linea.trim().isEmpty) {
      cerrarParrafo();
    } else if (titulo != null) {
      cerrarParrafo();
      bloques.add(BloqueMarkdown('titulo', [titulo[1]!]));
    } else if (numerada != null) {
      cerrarParrafo();
      if (ultimo?.tipo == 'numerada') {
        ultimo!.items.add(numerada[2]!);
      } else {
        bloques.add(BloqueMarkdown('numerada', [numerada[2]!], inicio: int.parse(numerada[1]!)));
      }
    } else if (vineta != null) {
      cerrarParrafo();
      if (ultimo?.tipo == 'vinetas') {
        ultimo!.items.add(vineta[1]!);
      } else {
        bloques.add(BloqueMarkdown('vinetas', [vineta[1]!]));
      }
    } else if (parrafo.isEmpty &&
        (ultimo?.tipo == 'numerada' || ultimo?.tipo == 'vinetas') &&
        RegExp(r'^\s+').hasMatch(linea)) {
      // Línea indentada debajo de un ítem: continuación de ese ítem.
      ultimo!.items[ultimo.items.length - 1] += ' ${linea.trim()}';
    } else {
      parrafo.add(linea.trim());
    }
  }
  cerrarParrafo();
  return bloques;
}
