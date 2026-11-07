import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Paleta tomada de frontend/src/index.css (variables --ui-*) para que la
/// app móvil se vea igual que la web.
class AppColors {
  static const fondo = Color(0xFF0E1017);
  static const barra = Color(0xFF12141C);
  static const tarjeta = Color(0xFF161924);
  static const borde = Color(0xFF262A36);
  static const texto = Color(0xFFE7E8EE);
  static const texto2 = Color(0xFFC9CCD6);
  static const texto3 = Color(0xFF9AA0B0);
  static const primario = Color(0xFF34D399);
  static const primarioTexto = Color(0xFF04291B);
  static const errorBg = Color(0xFF3D1D18);
  static const error = Color(0xFFFF9E8F);
  static const rolAdminBg = Color(0xFF3D1D18);
  static const rolAdminFg = Color(0xFFFF9E8F);
  static const rolColabBg = Color(0xFF10283F);
  static const rolColabFg = Color(0xFF7CC4FF);
  static const tipo = Color(0xFF7DD3FC);
  static const estereotipoBg = Color(0xFF1E2230);
  static const bordeEtiqueta = Color(0xFF2C3140);

  // Color de la IA (agente del chat grupal, sugerencias): --ia-*.
  static const ia = Color(0xFF22D3EE);
  static const iaClaro = Color(0xFF67E8F9);
  static const iaBg = Color(0xFF0B2229);
  static const iaBorde = Color(0xFF155E6E);
}

class AppTheme {
  /// Space Grotesk: títulos y botones (--font-heading).
  static TextStyle heading({
    double size = 16,
    FontWeight weight = FontWeight.w700,
    Color color = AppColors.texto,
  }) {
    return GoogleFonts.spaceGrotesk(fontSize: size, fontWeight: weight, color: color);
  }

  static ThemeData get oscuro {
    final base = ThemeData(
      brightness: Brightness.dark,
      useMaterial3: true,
      // IBM Plex Sans: cuerpo (--font-body).
      fontFamily: GoogleFonts.ibmPlexSans().fontFamily,
      scaffoldBackgroundColor: AppColors.fondo,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.primario,
        onPrimary: AppColors.primarioTexto,
        surface: AppColors.tarjeta,
        onSurface: AppColors.texto,
        error: AppColors.error,
      ),
    );

    return base.copyWith(
      textTheme: base.textTheme.apply(
        bodyColor: AppColors.texto,
        displayColor: AppColors.texto,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.barra,
        foregroundColor: AppColors.texto,
        elevation: 0,
        titleTextStyle: heading(size: 18),
        shape: const Border(bottom: BorderSide(color: AppColors.borde)),
      ),
      textSelectionTheme: const TextSelectionThemeData(
        cursorColor: AppColors.primario,
        selectionHandleColor: AppColors.primario,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.primario,
          foregroundColor: AppColors.primarioTexto,
          disabledBackgroundColor: AppColors.primario.withValues(alpha: 0.6),
          disabledForegroundColor: AppColors.primarioTexto,
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          textStyle: heading(size: 16, weight: FontWeight.w600),
        ),
      ),
    );
  }
}
