import 'package:shared_preferences/shared_preferences.dart';

import '../models/usuario.dart';
import 'api_client.dart';

/// Inicio de sesión, sesión guardada y cierre de sesión (CU19 - fase 1).
class AuthService {
  static const _claveToken = 'access_token';

  final ApiClient _api;

  AuthService({ApiClient? api}) : _api = api ?? ApiClient();

  Future<String?> obtenerToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_claveToken);
  }

  /// Hace login y devuelve el usuario. Lanza [ApiException] si falla.
  Future<Usuario> login(String email, String password) async {
    final data = await _api.post(
      '/auth/login',
      body: {'email': email, 'password': password},
    );
    final token = data['access_token'] as String;

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_claveToken, token);

    return obtenerUsuarioActual(token);
  }

  Future<Usuario> obtenerUsuarioActual(String token) async {
    final data = await _api.get('/auth/me', token: token);
    return Usuario.fromJson(data as Map<String, dynamic>);
  }

  /// Si hay un token guardado y sigue siendo válido devuelve el usuario.
  /// Devuelve null si no hay sesión o expiró. Lanza [ApiException] si no
  /// hay conexión (para que la pantalla de arranque ofrezca reintentar).
  Future<Usuario?> restaurarSesion() async {
    final token = await obtenerToken();
    if (token == null) return null;

    try {
      return await obtenerUsuarioActual(token);
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        await logout();
        return null;
      }
      rethrow;
    }
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_claveToken);
  }
}
