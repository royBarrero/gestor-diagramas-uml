import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Logo + nombre de la app (igual a la "marca" del AuthPanel web).
class Marca extends StatelessWidget {
  const Marca({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppColors.primario,
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(Icons.account_tree_outlined,
              color: AppColors.primarioTexto, size: 22),
        ),
        const SizedBox(width: 12),
        Flexible(
          child: Text('Gestor de Diagramas UML', style: AppTheme.heading(size: 18)),
        ),
      ],
    );
  }
}
