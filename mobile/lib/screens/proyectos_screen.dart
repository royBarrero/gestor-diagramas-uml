import 'package:flutter/material.dart';

import '../models/proyecto.dart';
import '../models/usuario.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/proyecto_service.dart';
import '../theme/app_theme.dart';
import '../widgets/avatar_usuario.dart';
import '../widgets/mensaje_error.dart';
import '../widgets/proyecto_card.dart';
import 'login_screen.dart';
import 'proyecto_screen.dart';

enum _FiltroRol { todos, administrador, colaborador }

/// CU19 - Paso 2: el sistema muestra la lista de proyectos en los que
/// participa el usuario (versión móvil y solo lectura del Dashboard web).
class ProyectosScreen extends StatefulWidget {
  final Usuario usuario;

  const ProyectosScreen({super.key, required this.usuario});

  @override
  State<ProyectosScreen> createState() => _ProyectosScreenState();
}

class _ProyectosScreenState extends State<ProyectosScreen> {
  final _servicio = ProyectoService();

  List<Proyecto> _proyectos = [];
  bool _cargando = true;
  ApiException? _error;
  _FiltroRol _filtro = _FiltroRol.todos;

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  Future<void> _cargar() async {
    setState(() => _error = null);
    try {
      final proyectos = await _servicio.misProyectos();
      if (!mounted) return;
      setState(() => _proyectos = proyectos);
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        await _cerrarSesion();
        return;
      }
      if (!mounted) return;
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  Future<void> _cerrarSesion() async {
    await AuthService().logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  Future<void> _confirmarCerrarSesion() async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.tarjeta,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: AppColors.borde),
        ),
        title: Text('Cerrar sesión', style: AppTheme.heading(size: 20)),
        content: const Text('¿Querés cerrar tu sesión en este dispositivo?',
            style: TextStyle(color: AppColors.texto2)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar', style: TextStyle(color: AppColors.texto2)),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(minimumSize: const Size(0, 40)),
            child: const Text('Cerrar sesión'),
          ),
        ],
      ),
    );
    if (confirmar == true) await _cerrarSesion();
  }

  void _abrir(Proyecto proyecto) {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ProyectoScreen(proyecto: proyecto)),
    );
  }

  List<Proyecto> get _visibles => switch (_filtro) {
        _FiltroRol.todos => _proyectos,
        _FiltroRol.administrador => _proyectos.where((p) => p.esAdministrador).toList(),
        _FiltroRol.colaborador => _proyectos.where((p) => !p.esAdministrador).toList(),
      };

  @override
  Widget build(BuildContext context) {
    final usuario = widget.usuario;
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 16,
        title: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: AppColors.primario,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.account_tree_outlined, color: AppColors.primarioTexto, size: 18),
            ),
            const SizedBox(width: 10),
            const Flexible(child: Text('Gestor UML')),
          ],
        ),
        actions: [
          AvatarUsuario(id: usuario.id, nombre: usuario.nombre, tamano: 32),
          IconButton(
            tooltip: 'Cerrar sesión',
            icon: const Icon(Icons.logout, color: AppColors.texto3),
            onPressed: _confirmarCerrarSesion,
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: RefreshIndicator(
        color: AppColors.primario,
        backgroundColor: AppColors.tarjeta,
        onRefresh: _cargar,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 24, 16, 32),
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Flexible(child: Text('Tus proyectos', style: AppTheme.heading(size: 28))),
                const SizedBox(width: 10),
                if (!_cargando && _error == null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      '${_proyectos.length} proyecto${_proyectos.length == 1 ? '' : 's'}',
                      style: const TextStyle(fontSize: 15, color: AppColors.texto3),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              'Consultá el diagrama, el historial y el chat de tus proyectos. '
              'Para editar, abrilos desde la web.',
              style: TextStyle(fontSize: 15, height: 1.5, color: AppColors.texto2),
            ),
            const SizedBox(height: 20),
            ..._contenido(),
          ],
        ),
      ),
    );
  }

  List<Widget> _contenido() {
    if (_cargando) {
      return const [
        SizedBox(height: 60),
        Center(child: CircularProgressIndicator(color: AppColors.primario)),
      ];
    }

    if (_error != null) {
      return [
        MensajeError(
          _error!.sinConexion
              ? 'No es posible cargar la información de tus proyectos. Revisá tu conexión a internet.'
              : _error!.mensaje,
          icono: _error!.sinConexion ? Icons.wifi_off : Icons.error_outline,
        ),
        const SizedBox(height: 16),
        OutlinedButton.icon(
          onPressed: () {
            setState(() => _cargando = true);
            _cargar();
          },
          icon: const Icon(Icons.refresh, size: 18),
          label: const Text('Reintentar'),
          style: OutlinedButton.styleFrom(
            foregroundColor: AppColors.texto,
            side: const BorderSide(color: AppColors.borde),
            minimumSize: const Size.fromHeight(44),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          ),
        ),
      ];
    }

    // Flujo alterno: el usuario no participa en ningún proyecto.
    if (_proyectos.isEmpty) {
      return const [
        _EstadoVacio(
          icono: Icons.folder_off_outlined,
          titulo: 'Todavía no participás en ningún proyecto',
          texto: 'Cuando crees un proyecto o te inviten a uno desde la web, va a aparecer acá.',
        ),
      ];
    }

    final visibles = _visibles;
    return [
      _Filtros(
        actual: _filtro,
        total: _proyectos.length,
        onCambiar: (f) => setState(() => _filtro = f),
      ),
      const SizedBox(height: 20),
      if (visibles.isEmpty)
        _EstadoVacio(
          icono: _filtro == _FiltroRol.colaborador ? Icons.group_outlined : Icons.shield_outlined,
          titulo: _filtro == _FiltroRol.colaborador
              ? 'Todavía no sos colaborador en ningún proyecto'
              : 'Todavía no administrás ningún proyecto',
          texto: 'Cambiá el filtro para ver el resto de tus proyectos.',
        ),
      for (final proyecto in visibles) ...[
        ProyectoCard(proyecto: proyecto, onAbrir: () => _abrir(proyecto)),
        const SizedBox(height: 16),
      ],
    ];
  }
}

/// Chips de filtro por rol (iguales a `.filtro` / `.filtroActivo` de la web).
class _Filtros extends StatelessWidget {
  final _FiltroRol actual;
  final int total;
  final ValueChanged<_FiltroRol> onCambiar;

  const _Filtros({required this.actual, required this.total, required this.onCambiar});

  @override
  Widget build(BuildContext context) {
    final opciones = {
      _FiltroRol.todos: 'Todos ($total)',
      _FiltroRol.administrador: 'Soy administrador',
      _FiltroRol.colaborador: 'Soy colaborador',
    };

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final entrada in opciones.entries) ...[
            _Chip(
              etiqueta: entrada.value,
              activo: entrada.key == actual,
              onTap: () => onCambiar(entrada.key),
            ),
            const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String etiqueta;
  final bool activo;
  final VoidCallback onTap;

  const _Chip({required this.etiqueta, required this.activo, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: activo ? AppColors.texto : AppColors.barra,
      shape: StadiumBorder(side: BorderSide(color: activo ? AppColors.texto : AppColors.borde)),
      child: InkWell(
        customBorder: const StadiumBorder(),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
          child: Text(
            etiqueta,
            style: TextStyle(
              fontSize: 14,
              fontWeight: activo ? FontWeight.w600 : FontWeight.w500,
              color: activo ? AppColors.fondo : AppColors.texto2,
            ),
          ),
        ),
      ),
    );
  }
}

/// Estado vacío con borde punteado (`.vacio` de la web; borde liso en Flutter).
class _EstadoVacio extends StatelessWidget {
  final IconData icono;
  final String titulo;
  final String texto;

  const _EstadoVacio({required this.icono, required this.titulo, required this.texto});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 40),
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.borde),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: AppColors.tarjeta,
              shape: BoxShape.circle,
              border: Border.all(color: AppColors.borde),
            ),
            child: Icon(icono, color: AppColors.texto3, size: 26),
          ),
          const SizedBox(height: 14),
          Text(
            titulo,
            textAlign: TextAlign.center,
            style: AppTheme.heading(size: 18, weight: FontWeight.w600, color: AppColors.texto2),
          ),
          const SizedBox(height: 6),
          Text(texto,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 15, color: AppColors.texto3)),
        ],
      ),
    );
  }
}
