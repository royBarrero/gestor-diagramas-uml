import 'package:flutter/foundation.dart';

/// Configuración de la API del backend (FastAPI).
///
/// Se puede sobreescribir al ejecutar:
///   flutter run --dart-define=API_URL=http://192.168.0.10:8000
/// Si no se indica, se elige según la plataforma:
///   - Emulador Android: 10.0.2.2 es el "localhost" de la PC.
///   - Chrome / Windows: localhost directo.
class ApiConfig {
  static const String _apiUrlDefinida = String.fromEnvironment('API_URL');

  static String get baseUrl {
    if (_apiUrlDefinida.isNotEmpty) return _apiUrlDefinida;
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://localhost:8000';
  }

  static const Duration timeout = Duration(seconds: 10);
}
