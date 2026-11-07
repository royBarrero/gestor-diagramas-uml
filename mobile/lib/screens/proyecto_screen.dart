import 'package:flutter/material.dart';

import '../models/diagrama.dart';
import '../models/proyecto.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/diagrama_service.dart';
import '../theme/app_theme.dart';
import '../utils/fecha_relativa.dart';
import '../widgets/diagrama/visor_diagrama.dart';
import '../widgets/mensaje_error.dart';
import 'login_screen.dart';

/// CU19 - Pasos 3 y 4: el usuario selecciona un proyecto y el sistema
/// muestra el diagrama de clases actual (solo lectura).
class ProyectoScreen extends StatefulWidget {
  final Proyecto proyecto;

  const ProyectoScreen({super.key, required this.proyecto});

  @override
  State<ProyectoScreen> createState() => _ProyectoScreenState();
}

class _ProyectoScreenState extends State<ProyectoScreen> {
  final _servicio = DiagramaService();

  Diagrama? _diagrama;
  ApiException? _error;
  bool _cargando = true;

  @override
  void initState() {
    super.initState();
    _cargar();
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
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        await AuthService().logout();
        if (!mounted) return;
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => const LoginScreen()),
          (_) => false,
        );
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
            onPressed: _cargando ? null : _cargar,
          ),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Resumen(proyecto: widget.proyecto, diagrama: _diagrama),
          Expanded(child: _cuerpo()),
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
