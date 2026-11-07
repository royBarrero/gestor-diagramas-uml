import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Caja de error con ícono, igual a `.error` de Login.module.css.
class MensajeError extends StatelessWidget {
  final String mensaje;
  final IconData icono;

  const MensajeError(this.mensaje, {super.key, this.icono = Icons.error_outline});

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 48),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.errorBg,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icono, color: AppColors.error, size: 19),
          const SizedBox(width: 10),
          Expanded(
            child: Text(mensaje,
                style: const TextStyle(color: AppColors.error, fontSize: 15)),
          ),
        ],
      ),
    );
  }
}
