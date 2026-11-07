import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';

/// Error de la API ya traducido a un mensaje para mostrar al usuario.
class ApiException implements Exception {
  final String mensaje;
  final int? statusCode;
  final bool sinConexion;

  const ApiException(this.mensaje, {this.statusCode, this.sinConexion = false});

  @override
  String toString() => mensaje;
}

const String mensajeSinConexion =
    'No hay conexión con el servidor. Revisá tu conexión a internet e intentá de nuevo.';

/// Cliente HTTP mínimo: agrega el token Bearer, aplica timeout y traduce
/// los errores de red / del backend a [ApiException].
class ApiClient {
  final http.Client _http;

  ApiClient({http.Client? httpClient}) : _http = httpClient ?? http.Client();

  Uri _uri(String path) => Uri.parse('${ApiConfig.baseUrl}$path');

  Map<String, String> _headers(String? token) => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Future<dynamic> get(String path, {String? token}) {
    return _enviar(() => _http.get(_uri(path), headers: _headers(token)));
  }

  Future<dynamic> post(String path, {Object? body, String? token}) {
    return _enviar(() => _http.post(
          _uri(path),
          headers: _headers(token),
          body: jsonEncode(body ?? {}),
        ));
  }

  Future<dynamic> _enviar(Future<http.Response> Function() peticion) async {
    final http.Response respuesta;
    try {
      respuesta = await peticion().timeout(ApiConfig.timeout);
    } on TimeoutException {
      throw const ApiException(mensajeSinConexion, sinConexion: true);
    } on http.ClientException {
      // SocketException en Android/iOS y fallos de red en web llegan acá.
      throw const ApiException(mensajeSinConexion, sinConexion: true);
    }

    final cuerpo = respuesta.body.isEmpty
        ? null
        : jsonDecode(utf8.decode(respuesta.bodyBytes));

    if (respuesta.statusCode >= 200 && respuesta.statusCode < 300) {
      return cuerpo;
    }

    String mensaje = 'Ocurrió un error inesperado. Intentá de nuevo.';
    if (cuerpo is Map && cuerpo['detail'] is String) {
      mensaje = cuerpo['detail'] as String;
    }
    throw ApiException(mensaje, statusCode: respuesta.statusCode);
  }
}
