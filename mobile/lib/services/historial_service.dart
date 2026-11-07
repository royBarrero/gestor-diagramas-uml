import '../models/historial.dart';
import 'api_client.dart';
import 'auth_service.dart';

/// Historial de cambios de un proyecto (CU19 - fase 4, solo lectura).
class HistorialService {
  static const limite = 50;

  final ApiClient _api;
  final AuthService _auth;

  HistorialService({ApiClient? api, AuthService? auth})
      : _api = api ?? ApiClient(),
        _auth = auth ?? AuthService();

  /// Del más reciente al más antiguo. `antesDe` es el id de la última entrada cargada.
  Future<List<EntradaHistorial>> listar(
    int proyectoId, {
    int? usuarioId,
    String? claseId,
    int? antesDe,
  }) async {
    final query = Uri(queryParameters: {
      'limite': '$limite',
      if (usuarioId != null) 'usuario_id': '$usuarioId',
      'clase_id': ?claseId,
      if (antesDe != null) 'antes_de': '$antesDe',
    }).query;
    final token = await _auth.obtenerToken();
    final data = await _api.get('/proyectos/$proyectoId/historial?$query', token: token);
    return (data as List)
        .map((e) => EntradaHistorial.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<FiltrosHistorial> filtros(int proyectoId) async {
    final token = await _auth.obtenerToken();
    final data = await _api.get('/proyectos/$proyectoId/historial/filtros', token: token);
    return FiltrosHistorial.fromJson(data as Map<String, dynamic>);
  }
}
