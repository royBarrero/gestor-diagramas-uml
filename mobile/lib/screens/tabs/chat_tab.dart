import 'package:flutter/material.dart';

import '../../models/mensaje.dart';
import '../../services/api_client.dart';
import '../../services/chat_service.dart';
import '../../theme/app_theme.dart';
import '../../utils/avatar.dart';
import '../../utils/fecha_relativa.dart';
import '../../utils/sesion.dart';
import '../../widgets/mensaje_error.dart';
import '../../widgets/mensaje_formateado.dart';
import 'historial_tab.dart' show AvatarAgente, AvatarInicial;

const _etiquetaEstado = {
  'confirmada': 'Confirmado',
  'cancelada': 'Cancelado',
  'deshecha': 'Deshecho',
};

/// CU19 - Paso 5: chat grupal del proyecto, con las sugerencias del agente
/// de IA. Solo lectura: no hay caja de texto ni botones de confirmar/deshacer.
class ChatTab extends StatefulWidget {
  final int proyectoId;
  final int usuarioId;

  const ChatTab({super.key, required this.proyectoId, required this.usuarioId});

  @override
  State<ChatTab> createState() => ChatTabState();
}

class ChatTabState extends State<ChatTab> {
  final _servicio = ChatService();

  List<Mensaje> _mensajes = []; // del más viejo al más nuevo
  bool _cargando = true;
  bool _cargandoMas = false;
  bool _hayAnteriores = false;
  bool _agenteEscribiendo = false;
  ApiException? _error;

  @override
  void initState() {
    super.initState();
    recargar();
  }

  Future<void> recargar() async {
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      final mensajes = await _servicio.listar(widget.proyectoId);
      if (!mounted) return;
      setState(() {
        _mensajes = mensajes;
        _hayAnteriores = mensajes.length == ChatService.limite;
      });
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        if (mounted) await cerrarSesionYVolverAlLogin(context);
        return;
      }
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  /// Mensaje nuevo que llegó por el socket.
  void agregar(Mensaje mensaje) {
    if (_mensajes.any((m) => m.id == mensaje.id)) return;
    setState(() => _mensajes = [..._mensajes, mensaje]);
  }

  /// Mensaje que cambió (ej. el estado de un cambio del agente, CU17).
  void actualizar(Mensaje mensaje) {
    final i = _mensajes.indexWhere((m) => m.id == mensaje.id);
    if (i == -1) return;
    setState(() => _mensajes = [..._mensajes]..[i] = mensaje);
  }

  void agenteEscribiendo(bool activo) {
    if (_agenteEscribiendo != activo) setState(() => _agenteEscribiendo = activo);
  }

  Future<void> _cargarAnteriores() async {
    setState(() => _cargandoMas = true);
    try {
      final mas = await _servicio.listar(widget.proyectoId, antesDe: _mensajes.first.id);
      if (!mounted) return;
      setState(() {
        _mensajes = [...mas, ..._mensajes];
        _hayAnteriores = mas.length == ChatService.limite;
      });
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.mensaje)));
      }
    } finally {
      if (mounted) setState(() => _cargandoMas = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Expanded(child: _cuerpo()),
        Container(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
          decoration: const BoxDecoration(border: Border(top: BorderSide(color: AppColors.borde))),
          child: const Row(
            children: [
              Icon(Icons.visibility_outlined, size: 16, color: AppColors.texto3),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Solo lectura. Para escribir al equipo o consultar a la IA, usá la web.',
                  style: TextStyle(fontSize: 13, color: AppColors.texto3),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _cuerpo() {
    if (_error != null && _mensajes.isEmpty) {
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          MensajeError(
            _error!.sinConexion
                ? 'No es posible cargar el chat. Revisá tu conexión a internet.'
                : _error!.mensaje,
            icono: _error!.sinConexion ? Icons.wifi_off : Icons.error_outline,
          ),
          const SizedBox(height: 12),
          Center(child: _botonSecundario('Reintentar', recargar)),
        ],
      );
    }
    if (_cargando && _mensajes.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: AppColors.primario));
    }
    if (_mensajes.isEmpty && !_agenteEscribiendo) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Todavía no hay mensajes en el chat del proyecto.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 14, height: 1.5, color: AppColors.texto3),
          ),
        ),
      );
    }

    // reverse: arranca abajo, en el último mensaje, como un chat.
    final items = <Widget>[
      if (_agenteEscribiendo) const _AgenteEscribiendo(),
      for (final m in _mensajes.reversed) _MensajeWidget(mensaje: m, usuarioId: widget.usuarioId),
    ];
    return ListView.separated(
      reverse: true,
      padding: const EdgeInsets.all(16),
      itemCount: items.length + (_hayAnteriores ? 1 : 0),
      separatorBuilder: (_, _) => const SizedBox(height: 16),
      itemBuilder: (context, i) {
        if (i == items.length) {
          return Center(
            child: _botonSecundario(
              _cargandoMas ? 'Cargando…' : 'Cargar mensajes anteriores',
              _cargandoMas ? null : _cargarAnteriores,
            ),
          );
        }
        return items[i];
      },
    );
  }

  Widget _botonSecundario(String texto, VoidCallback? onTap) {
    return OutlinedButton(
      onPressed: onTap,
      style: OutlinedButton.styleFrom(
        backgroundColor: AppColors.tarjeta,
        foregroundColor: AppColors.texto2,
        side: const BorderSide(color: AppColors.borde),
        minimumSize: const Size(0, 32),
        padding: const EdgeInsets.symmetric(horizontal: 12),
        textStyle: const TextStyle(fontSize: 13),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      child: Text(texto),
    );
  }
}

class _MensajeWidget extends StatelessWidget {
  final Mensaje mensaje;
  final int usuarioId;

  const _MensajeWidget({required this.mensaje, required this.usuarioId});

  @override
  Widget build(BuildContext context) {
    final m = mensaje;

    if (m.tipo == 'sistema') {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          border: Border.all(color: AppColors.borde),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(m.texto,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 13, color: AppColors.texto3)),
      );
    }

    final hora = Text(formatearHora(m.createdAt),
        style: const TextStyle(fontSize: 12, color: AppColors.texto3));

    if (m.tipo == 'agente') {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const AvatarAgente(),
          const SizedBox(width: 10),
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: AppColors.iaBg,
                border: Border.all(color: AppColors.iaBorde),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(4),
                  topRight: Radius.circular(12),
                  bottomLeft: Radius.circular(12),
                  bottomRight: Radius.circular(12),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      const Text('Agente IA',
                          style: TextStyle(
                              fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.iaClaro)),
                      hora,
                      if (m.sugerenciaResuelta) const _Resuelta(),
                    ],
                  ),
                  if (m.destinoId != null) ...[
                    const SizedBox(height: 3),
                    Text.rich(
                      TextSpan(children: [
                        const TextSpan(text: 'Para '),
                        TextSpan(
                          text: m.destinoId == usuarioId ? 'vos' : (m.destinoNombre ?? ''),
                          style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.iaClaro),
                        ),
                      ]),
                      style: const TextStyle(fontSize: 12, color: AppColors.texto2),
                    ),
                  ],
                  const SizedBox(height: 3),
                  MensajeFormateado(m.texto),
                  if (_estadoAccion(m) case final estado?) ...[
                    const SizedBox(height: 8),
                    Text(estado, style: const TextStyle(fontSize: 13, color: AppColors.texto3)),
                  ],
                ],
              ),
            ),
          ),
        ],
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AvatarInicial(nombre: m.autorNombre, color: colorPorUsuario(m.autorId ?? 0)),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 6,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(
                    m.autorId == usuarioId ? 'Vos' : (m.autorNombre ?? ''),
                    style: const TextStyle(
                        fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.texto),
                  ),
                  hora,
                ],
              ),
              const SizedBox(height: 3),
              Text.rich(_conMenciones(m.texto),
                  style: const TextStyle(fontSize: 14, height: 1.5, color: AppColors.texto)),
            ],
          ),
        ),
      ],
    );
  }

  /// Estado de un cambio propuesto por el agente (CU17), sin los botones.
  String? _estadoAccion(Mensaje m) {
    final accion = m.accion;
    if (accion == null) return null;
    final etiqueta = _etiquetaEstado[accion.estado];
    if (etiqueta != null) return etiqueta;
    if (accion.estado == 'pendiente') {
      return accion.idSolicitante == usuarioId
          ? 'Esperando tu confirmación (confirmalo desde la web)'
          : 'Esperando la confirmación de ${m.destinoNombre ?? 'quien lo pidió'}';
    }
    return null; // aplicada: en la web muestra "Deshacer"
  }

  /// Resalta las menciones @IA, como TextoConMenciones de la web.
  TextSpan _conMenciones(String texto) {
    final spans = <InlineSpan>[];
    texto.splitMapJoin(
      RegExp(r'(?<!\w)@ia\b', caseSensitive: false),
      onMatch: (m) {
        spans.add(TextSpan(
          text: m[0],
          style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.ia),
        ));
        return '';
      },
      onNonMatch: (s) {
        if (s.isNotEmpty) spans.add(TextSpan(text: s));
        return '';
      },
    );
    return TextSpan(children: spans);
  }
}

/// Tres puntos que rebotan mientras el agente responde (`.escribiendo` de la web).
class _AgenteEscribiendo extends StatefulWidget {
  const _AgenteEscribiendo();

  @override
  State<_AgenteEscribiendo> createState() => _AgenteEscribiendoState();
}

class _AgenteEscribiendoState extends State<_AgenteEscribiendo> with SingleTickerProviderStateMixin {
  late final AnimationController _anim =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))..repeat();

  @override
  void dispose() {
    _anim.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const AvatarAgente(),
        const SizedBox(width: 10),
        Semantics(
          label: 'El agente está escribiendo',
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: AppColors.iaBg,
              border: Border.all(color: AppColors.iaBorde),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(12),
                bottomLeft: Radius.circular(12),
                bottomRight: Radius.circular(12),
              ),
            ),
            child: AnimatedBuilder(
              animation: _anim,
              builder: (context, _) => Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (var i = 0; i < 3; i++) ...[
                    if (i > 0) const SizedBox(width: 5),
                    _punto(((_anim.value - i * 0.125) % 1.0)),
                  ],
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  /// Igual a la animación `rebote`: sube y se ilumina en el 30% del ciclo.
  Widget _punto(double t) {
    final fase = t < 0.6 ? (t < 0.3 ? t / 0.3 : (0.6 - t) / 0.3) : 0.0;
    return Transform.translate(
      offset: Offset(0, -4 * fase),
      child: Container(
        width: 7,
        height: 7,
        decoration: BoxDecoration(
          color: AppColors.ia.withValues(alpha: 0.5 + 0.5 * fase),
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}

class _Resuelta extends StatelessWidget {
  const _Resuelta();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.primario),
        borderRadius: BorderRadius.circular(999),
      ),
      child: const Text('Resuelta',
          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.primario)),
    );
  }
}
