import '../models/diagrama.dart';
import 'api_client.dart';
import 'auth_service.dart';

/// Lectura del diagrama de un proyecto (CU19 - fase 3, solo lectura).
class DiagramaService {
  final ApiClient _api;
  final AuthService _auth;

  DiagramaService({ApiClient? api, AuthService? auth})
      : _api = api ?? ApiClient(),
        _auth = auth ?? AuthService();

  /// Devuelve la versión actual: si alguien lo está editando en la web, el
  /// backend responde con la versión en vivo, no la última guardada.
  Future<Diagrama> obtenerDeProyecto(int proyectoId) async {
    final token = await _auth.obtenerToken();
    final data = await _api.get('/diagramas/proyecto/$proyectoId', token: token);
    return Diagrama.fromJson(data as Map<String, dynamic>);
  }
}
