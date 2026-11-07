import '../models/proyecto.dart';
import 'api_client.dart';
import 'auth_service.dart';

/// Consulta de proyectos (solo lectura) para la app móvil (CU19 - fase 2).
class ProyectoService {
  final ApiClient _api;
  final AuthService _auth;

  ProyectoService({ApiClient? api, AuthService? auth})
      : _api = api ?? ApiClient(),
        _auth = auth ?? AuthService();

  /// Proyectos en los que participa el usuario (como administrador o colaborador).
  Future<List<Proyecto>> misProyectos() async {
    final token = await _auth.obtenerToken();
    final data = await _api.get('/proyectos/mis-proyectos', token: token);
    return (data as List)
        .map((p) => Proyecto.fromJson(p as Map<String, dynamic>))
        .toList();
  }
}
