import 'package:flutter/material.dart';

import '../models/diagrama.dart';
import '../models/proyecto.dart';
import '../models/usuario.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/diagrama_service.dart';
import '../services/tiempo_real_service.dart';
import '../theme/app_theme.dart';
import '../utils/fecha_relativa.dart';
import '../utils/sesion.dart';
import '../widgets/diagrama/visor_diagrama.dart';
import '../widgets/mensaje_error.dart';
import 'tabs/chat_tab.dart';
import 'tabs/historial_tab.dart';

/// CU19 - Pasos 3 a 5: el usuario selecciona un proyecto y consulta, en
/// solo lectura, el diagrama de clases actual, el historial y el chat.
class ProyectoScreen extends StatefulWidget {
  final Proyecto proyecto;
  final Usuario usuario;

  const ProyectoScreen({super.key, required this.proyecto, required this.usuario});

  @override
  State<ProyectoScreen> createState() => _ProyectoScreenState();
}

class _ProyectoScreenState extends State<ProyectoScreen> with SingleTickerProviderStateMixin {
  final _servicio = DiagramaService();
  final _historialKey = GlobalKey<HistorialTabState>();
  final _chatKey = GlobalKey<ChatTabState>();
  late final TabController _tabs = TabController(length: 3, vsync: this)
    ..addListener(() => setState(() {}));

  Diagrama? _diagrama;
  ApiException? _error;
  bool _cargando = true;
  TiempoRealService? _tiempoReal;
  EstadoConexion? _estadoConexion;

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  @override
  void dispose() {
    _tiempoReal?.cerrar();
    _tabs.dispose();
    super.dispose();
  }

  /// Socket en modo lectura: lo que se edita en la web llega solo (CU07 → CU19).
  Future<void> _conectarTiempoReal(int diagramaId) async {
    final token = await AuthService().obtenerToken();
    if (!mounted || token == null || _tiempoReal != null) return;

    final servicio = TiempoRealService(diagramaId: diagramaId, token: token)
      // En cada conexión (también al reconectar) se pone al día con lo que pasó
      // mientras no estaba conectado, como hace la pizarra web.
      ..onConectado = _recargarTodo
      ..onEstado = (estado) {
        if (mounted) setState(() => _estadoConexion = estado);
      }
      ..onCambioDiagrama = (contenido) {
        final actual = _diagrama;
        if (!mounted || actual == null) return;
        setState(() {
          _diagrama = Diagrama.desdeContenido(
            id: actual.id,
            contenido: contenido,
            updatedAt: DateTime.now(),
            anterior: actual,
          );
        });
      }
      ..onMensaje = ((m) => _chatKey.currentState?.agregar(m))
      ..onMensajeActualizado = ((m) => _chatKey.currentState?.actualizar(m))
      ..onAgenteEscribiendo = ((activo) => _chatKey.currentState?.agenteEscribiendo(activo))
      ..onHistorial = ((e) => _historialKey.currentState?.agregar(e));
    _tiempoReal = servicio;
    servicio.conectar();
  }

  /// El botón de actualizar recarga las tres pestañas.
  void _recargarTodo() {
    _cargar();
    _historialKey.currentState?.recargar();
    _chatKey.currentState?.recargar();
  }

  Future<void> _cargar() async {
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      final diagrama = await _servicio.obtenerDeProyecto(widget.proyecto.id);
      if (!mounted) return;
      setState(() => _diagrama = diagrama);
      _conectarTiempoReal(diagrama.id);
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        if (mounted) await cerrarSesionYVolverAlLogin(context);
        return;
      }
      if (!mounted) return;
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.proyecto.nombre, overflow: TextOverflow.ellipsis),
        actions: [
          IconButton(
            tooltip: 'Actualizar',
            icon: const Icon(Icons.refresh, color: AppColors.texto3),
            onPressed: _cargando ? null : _recargarTodo,
          ),
        ],
        bottom: TabBar(
          controller: _tabs,
          indicatorColor: AppColors.primario,
          indicatorWeight: 2,
          labelColor: AppColors.texto,
          unselectedLabelColor: AppColors.texto3,
          labelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          dividerColor: AppColors.borde,
          tabs: const [Tab(text: 'Diagrama'), Tab(text: 'Historial'), Tab(text: 'Chat')],
        ),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Resumen(proyecto: widget.proyecto, diagrama: _diagrama),
          ?_avisoConexion(),
          // IndexedStack (no TabBarView): las pestañas quedan montadas, no se
          // recargan al cambiar, y deslizar no choca con mover el diagrama.
          Expanded(
            child: IndexedStack(
              index: _tabs.index,
              children: [
                _cuerpo(),
                HistorialTab(key: _historialKey, proyectoId: widget.proyecto.id, diagrama: _diagrama),
                ChatTab(key: _chatKey, proyectoId: widget.proyecto.id, usuarioId: widget.usuario.id),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Aviso de conexión en vivo, como el de PanelLateral.jsx.
  Widget? _avisoConexion() {
    final texto = switch (_estadoConexion) {
      EstadoConexion.reconectando => 'Sin conexión en vivo, reintentando…',
      EstadoConexion.rechazado =>
        'No se pudo conectar en vivo. Usá Actualizar o volvé a iniciar sesión.',
      _ => null,
    };
    if (texto == null) return null;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: AppColors.errorBg,
      child: Row(
        children: [
          const Icon(Icons.wifi_off, size: 16, color: AppColors.error),
          const SizedBox(width: 8),
          Expanded(child: Text(texto, style: const TextStyle(fontSize: 13, color: AppColors.error))),
        ],
      ),
    );
  }

  Widget _cuerpo() {
    if (_cargando && _diagrama == null) {
      return const Center(child: CircularProgressIndicator(color: AppColors.primario));
    }

    if (_error != null && _diagrama == null) {
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          MensajeError(
            _error!.sinConexion
                ? 'No es posible cargar la información del proyecto. Revisá tu conexión a internet.'
                : _error!.mensaje,
            icono: _error!.sinConexion ? Icons.wifi_off : Icons.error_outline,
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: _cargar,
            icon: const Icon(Icons.refresh, size: 18),
            label: const Text('Reintentar'),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.texto,
              side: const BorderSide(color: AppColors.borde),
              minimumSize: const Size.fromHeight(44),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
          ),
        ],
      );
    }

    final diagrama = _diagrama!;
    if (diagrama.clases.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.account_tree_outlined, size: 40, color: AppColors.texto3),
              SizedBox(height: 12),
              Text(
                'Este proyecto todavía no tiene clases en su diagrama.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 15, color: AppColors.texto3),
              ),
            ],
          ),
        ),
      );
    }

    return Stack(
      children: [
        Positioned.fill(child: VisorDiagrama(diagrama: diagrama)),
        // Si falla una recarga se sigue mostrando el último diagrama cargado.
        if (_error != null)
          Positioned(
            left: 12,
            right: 12,
            top: 12,
            child: MensajeError(
              _error!.sinConexion ? 'Sin conexión: se muestra la última versión cargada.' : _error!.mensaje,
              icono: _error!.sinConexion ? Icons.wifi_off : Icons.error_outline,
            ),
          ),
        if (_cargando)
          const Positioned(
            left: 0,
            right: 0,
            top: 0,
            child: LinearProgressIndicator(minHeight: 2, color: AppColors.primario),
          ),
      ],
    );
  }
}

/// Estado y avance del proyecto: rol, cantidad de clases/relaciones y
/// cuándo fue el último cambio.
class _Resumen extends StatelessWidget {
  final Proyecto proyecto;
  final Diagrama? diagrama;

  const _Resumen({required this.proyecto, required this.diagrama});

  @override
  Widget build(BuildContext context) {
    final clases = diagrama?.clases.length ?? proyecto.totalClases;
    final relaciones = diagrama?.relaciones.length ?? proyecto.totalRelaciones;
    final actualizado = diagrama?.updatedAt ?? proyecto.updatedAt;
    const estilo = TextStyle(fontSize: 13, color: AppColors.texto2);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: const BoxDecoration(
        color: AppColors.barra,
        border: Border(bottom: BorderSide(color: AppColors.borde)),
      ),
      child: Wrap(
        spacing: 12,
        runSpacing: 6,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          _Etiqueta(
            texto: 'Solo lectura',
            icono: Icons.visibility_outlined,
            fondo: AppColors.tarjeta,
            color: AppColors.texto2,
          ),
          Text(
            '$clases clase${clases == 1 ? '' : 's'} · '
            '$relaciones relaci${relaciones == 1 ? 'ón' : 'ones'}',
            style: estilo,
          ),
          Text(fechaRelativa(actualizado), style: estilo.copyWith(color: AppColors.texto3)),
        ],
      ),
    );
  }
}

class _Etiqueta extends StatelessWidget {
  final String texto;
  final IconData icono;
  final Color fondo;
  final Color color;

  const _Etiqueta({required this.texto, required this.icono, required this.fondo, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: fondo,
        border: Border.all(color: AppColors.borde),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icono, size: 14, color: color),
          const SizedBox(width: 5),
          Text(texto, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
        ],
      ),
    );
  }
}
