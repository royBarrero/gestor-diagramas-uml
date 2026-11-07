import '../models/mensaje.dart';
import 'api_client.dart';
import 'auth_service.dart';

/// Chat grupal de un proyecto (CU19 - fase 4). Solo lectura: desde el móvil
/// no se envían mensajes.
class ChatService {
  static const limite = 50;

  final ApiClient _api;
  final AuthService _auth;

  ChatService({ApiClient? api, AuthService? auth})
      : _api = api ?? ApiClient(),
        _auth = auth ?? AuthService();

  /// Del más viejo al más nuevo: los últimos [limite], o los anteriores a `antesDe`.
  Future<List<Mensaje>> listar(int proyectoId, {int? antesDe}) async {
    final query = Uri(queryParameters: {
      'limite': '$limite',
      if (antesDe != null) 'antes_de': '$antesDe',
    }).query;
    final token = await _auth.obtenerToken();
    final data = await _api.get('/proyectos/$proyectoId/mensajes?$query', token: token);
    return (data as List).map((m) => Mensaje.fromJson(m as Map<String, dynamic>)).toList();
  }
}
