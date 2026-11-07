import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Campo con label arriba e ícono a la izquierda, equivalente al
/// componente CampoTexto de la web.
class CampoTexto extends StatefulWidget {
  final String label;
  final IconData icono;
  final String? placeholder;
  final TextEditingController controller;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final Iterable<String>? autofillHints;
  final bool esPassword;
  final ValueChanged<String>? onSubmitted;

  const CampoTexto({
    super.key,
    required this.label,
    required this.icono,
    required this.controller,
    this.placeholder,
    this.keyboardType,
    this.textInputAction,
    this.autofillHints,
    this.esPassword = false,
    this.onSubmitted,
  });

  @override
  State<CampoTexto> createState() => _CampoTextoState();
}

class _CampoTextoState extends State<CampoTexto> {
  bool _oculto = true;

  OutlineInputBorder _borde(Color color, double ancho) => OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: color, width: ancho),
      );

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(widget.label,
            style: const TextStyle(
                fontSize: 15, fontWeight: FontWeight.w500, color: AppColors.texto2)),
        const SizedBox(height: 8),
        TextField(
          controller: widget.controller,
          keyboardType: widget.keyboardType,
          textInputAction: widget.textInputAction,
          autofillHints: widget.autofillHints,
          obscureText: widget.esPassword && _oculto,
          autocorrect: !widget.esPassword,
          enableSuggestions: !widget.esPassword,
          onSubmitted: widget.onSubmitted,
          style: const TextStyle(fontSize: 15, color: AppColors.texto),
          decoration: InputDecoration(
            isDense: true,
            filled: true,
            fillColor: AppColors.tarjeta,
            hintText: widget.placeholder,
            hintStyle: const TextStyle(color: AppColors.texto3),
            contentPadding: const EdgeInsets.symmetric(vertical: 14),
            prefixIcon: Icon(widget.icono, color: AppColors.texto3, size: 19),
            suffixIcon: widget.esPassword
                ? IconButton(
                    tooltip: _oculto ? 'Mostrar contraseña' : 'Ocultar contraseña',
                    icon: Icon(
                      _oculto ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                      color: AppColors.texto3,
                      size: 19,
                    ),
                    onPressed: () => setState(() => _oculto = !_oculto),
                  )
                : null,
            enabledBorder: _borde(AppColors.borde, 1),
            focusedBorder: _borde(AppColors.primario, 2),
          ),
        ),
      ],
    );
  }
}
