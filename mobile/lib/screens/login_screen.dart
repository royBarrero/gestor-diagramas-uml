import 'package:flutter/material.dart';

import '../models/usuario.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../theme/app_theme.dart';
import '../widgets/campo_texto.dart';
import '../widgets/fondo_puntos.dart';
import '../widgets/marca.dart';
import '../widgets/mensaje_error.dart';
import 'home_screen.dart';

/// CU19 - Paso 1: el usuario inicia sesión en la app móvil.
class LoginScreen extends StatefulWidget {
  /// Mensaje inicial opcional (ej. sin conexión al restaurar la sesión).
  final String? mensajeInicial;

  const LoginScreen({super.key, this.mensajeInicial});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _auth = AuthService();
  final _email = TextEditingController();
  final _password = TextEditingController();

  String? _error;
  bool _sinConexion = false;
  bool _cargando = false;

  @override
  void initState() {
    super.initState();
    _error = widget.mensajeInicial;
    _sinConexion = widget.mensajeInicial != null;
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _entrar() async {
    final email = _email.text.trim();
    final password = _password.text;
    if (email.isEmpty || password.isEmpty) {
      setState(() {
        _error = 'Completá tu correo y tu contraseña.';
        _sinConexion = false;
      });
      return;
    }

    FocusScope.of(context).unfocus();
    setState(() {
      _error = null;
      _cargando = true;
    });

    try {
      final Usuario usuario = await _auth.login(email, password);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => HomeScreen(usuario: usuario)),
      );
    } on ApiException catch (e) {
      setState(() {
        _error = e.mensaje;
        _sinConexion = e.sinConexion;
      });
    } catch (_) {
      setState(() {
        _error = 'No se pudo iniciar sesión.';
        _sinConexion = false;
      });
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FondoPuntos(
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 32, 16, 32),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 400),
                child: AutofillGroup(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Marca(),
                      const SizedBox(height: 40),
                      Text('Iniciar sesión', style: AppTheme.heading(size: 28)),
                      const SizedBox(height: 8),
                      const Text(
                        'Accedé a tus proyectos y diagramas.',
                        style: TextStyle(fontSize: 16, color: AppColors.texto2),
                      ),
                      const SizedBox(height: 24),
                      CampoTexto(
                        label: 'Correo',
                        icono: Icons.mail_outline,
                        placeholder: 'tu@correo.com',
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        textInputAction: TextInputAction.next,
                        autofillHints: const [AutofillHints.email],
                      ),
                      const SizedBox(height: 18),
                      CampoTexto(
                        label: 'Contraseña',
                        icono: Icons.lock_outline,
                        placeholder: 'Tu contraseña',
                        controller: _password,
                        esPassword: true,
                        textInputAction: TextInputAction.done,
                        autofillHints: const [AutofillHints.password],
                        onSubmitted: (_) => _cargando ? null : _entrar(),
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 18),
                        MensajeError(
                          _error!,
                          icono: _sinConexion ? Icons.wifi_off : Icons.error_outline,
                        ),
                      ],
                      const SizedBox(height: 24),
                      FilledButton(
                        onPressed: _cargando ? null : _entrar,
                        child: _cargando
                            ? const Text('Entrando...')
                            : const Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text('Entrar'),
                                  SizedBox(width: 8),
                                  Icon(Icons.arrow_forward, size: 18),
                                ],
                              ),
                      ),
                      const SizedBox(height: 22),
                      const Text(
                        '¿No tenés cuenta? Registrate desde la web.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 15, color: AppColors.texto2),
                      ),
                      const SizedBox(height: 40),
                      const Text(
                        'Ingeniería de Software I · UAGRM',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 13, color: AppColors.texto3),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
