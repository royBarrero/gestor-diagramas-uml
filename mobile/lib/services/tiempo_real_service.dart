import 'package:socket_io_client/socket_io_client.dart' as io;

import '../config/api_config.dart';
import '../models/historial.dart';
import '../models/mensaje.dart';

enum EstadoConexion { conectando, conectado, reconectando, rechazado }

/// Socket del proyecto en modo lectura (CU19): recibe en vivo los cambios del
/// diagrama, el chat y el historial que genera la web. No envía nada.
class TiempoRealService {
  final io.Socket _socket;

  /// Se llama en cada conexión, también al reconectar: momento de ponerse al día.
  void Function()? onConectado;
  void Function(EstadoConexion estado)? onEstado;

  /// Contenido completo del diagrama (`nodes` / `edges`), como lo manda la web.
  void Function(Map<String, dynamic> contenido)? onCambioDiagrama;
  void Function(Mensaje mensaje)? onMensaje;
  void Function(Mensaje mensaje)? onMensajeActualizado;
  void Function(bool activo)? onAgenteEscribiendo;
  void Function(EntradaHistorial entrada)? onHistorial;

  TiempoRealService({required int diagramaId, required String token})
      : _socket = io.io(
          ApiConfig.baseUrl,
          io.OptionBuilder()
              .setTransports(['websocket'])
              .setAuth({'token': token})
              .setQuery({'diagramaId': '$diagramaId', 'modo': 'lectura'})
              .enableForceNew()
              .enableReconnection()
              .disableAutoConnect()
              .build(),
        ) {
    _socket
      ..on('connect', (_) {
        onEstado?.call(EstadoConexion.conectado);
        onConectado?.call();
      })
      ..on('disconnect', (_) => onEstado?.call(EstadoConexion.reconectando))
      // Si el servidor rechazó la conexión (ej. token vencido) no se reintenta solo.
      ..on('connect_error', (_) {
        onEstado?.call(_socket.active ? EstadoConexion.reconectando : EstadoConexion.rechazado);
      })
      ..on('cambio_diagrama', (data) {
        if (data is Map) onCambioDiagrama?.call(data.cast<String, dynamic>());
      })
      ..on('chat_mensaje', (data) {
        if (data is Map) onMensaje?.call(Mensaje.fromJson(data.cast<String, dynamic>()));
      })
      ..on('chat_mensaje_actualizado', (data) {
        if (data is Map) onMensajeActualizado?.call(Mensaje.fromJson(data.cast<String, dynamic>()));
      })
      ..on('chat_agente_escribiendo', (data) {
        if (data is Map) onAgenteEscribiendo?.call(data['activo'] == true);
      })
      ..on('historial_cambio', (data) {
        if (data is Map) onHistorial?.call(EntradaHistorial.fromJson(data.cast<String, dynamic>()));
      });
  }

  void conectar() {
    onEstado?.call(EstadoConexion.conectando);
    _socket.connect();
  }

  void cerrar() {
    _socket.dispose();
  }
}
