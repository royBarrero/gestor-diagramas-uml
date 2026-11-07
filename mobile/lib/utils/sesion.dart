import 'package:flutter/material.dart';

import '../screens/login_screen.dart';
import '../services/auth_service.dart';

/// Si el backend responde 401 (sesión vencida): borra el token y vuelve al login.
Future<void> cerrarSesionYVolverAlLogin(BuildContext context) async {
  await AuthService().logout();
  if (!context.mounted) return;
  Navigator.of(context).pushAndRemoveUntil(
    MaterialPageRoute(builder: (_) => const LoginScreen()),
    (_) => false,
  );
}
