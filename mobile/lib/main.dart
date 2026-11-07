import 'package:flutter/material.dart';

import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'services/api_client.dart';
import 'services/auth_service.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const GestorDiagramasApp());
}

class GestorDiagramasApp extends StatelessWidget {
  const GestorDiagramasApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Gestor de Diagramas UML',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.oscuro,
      home: const ArranqueScreen(),
    );
  }
}

/// Decide a dónde ir al abrir la app: si hay una sesión guardada válida va
/// directo al inicio; si no, al login.
class ArranqueScreen extends StatefulWidget {
  const ArranqueScreen({super.key});

  @override
  State<ArranqueScreen> createState() => _ArranqueScreenState();
}

class _ArranqueScreenState extends State<ArranqueScreen> {
  @override
  void initState() {
    super.initState();
    _restaurarSesion();
  }

  Future<void> _restaurarSesion() async {
    Widget destino;
    try {
      final usuario = await AuthService().restaurarSesion();
      destino = usuario != null ? HomeScreen(usuario: usuario) : const LoginScreen();
    } on ApiException catch (e) {
      destino = LoginScreen(mensajeInicial: e.mensaje);
    }

    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => destino));
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator(color: AppColors.primario)),
    );
  }
}
