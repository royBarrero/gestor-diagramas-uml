import 'package:flutter/material.dart';

import '../../models/diagrama.dart';
import '../../models/historial.dart';
import '../../services/api_client.dart';
import '../../services/historial_service.dart';
import '../../theme/app_theme.dart';
import '../../utils/fecha_relativa.dart';
import '../../utils/sesion.dart';
import '../../widgets/mensaje_error.dart';

/// CU19 - Paso 5: historial de cambios del proyecto (versión de solo lectura
/// de HistorialCambios.jsx), con filtros por integrante y por clase.
class HistorialTab extends StatefulWidget {
  final int proyectoId;

  /// Diagrama actual, para saber qué clases siguen existiendo.
  final Diagrama? diagrama;

  const HistorialTab({super.key, required this.proyectoId, required this.diagrama});

  @override
  State<HistorialTab> createState() => HistorialTabState();
}

class HistorialTabState extends State<HistorialTab> {
  final _servicio = HistorialService();

  List<EntradaHistorial> _entradas = [];
  FiltrosHistorial _opciones = FiltrosHistorial.vacio;
  int? _usuarioId;
  String? _claseId;
  bool _cargando = true;
  bool _cargandoMas = false;
  bool _hayAnteriores = false;
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
      final resultados = await Future.wait([
        _servicio.listar(widget.proyectoId, usuarioId: _usuarioId, claseId: _claseId),
        _servicio.filtros(widget.proyectoId),
      ]);
      if (!mounted) return;
      final entradas = resultados[0] as List<EntradaHistorial>;
      setState(() {
        _entradas = entradas;
        _opciones = resultados[1] as FiltrosHistorial;
        _hayAnteriores = entradas.length == HistorialService.limite;
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

  /// Una entrada que llegó por el socket: va arriba si cumple los filtros activos.
  void agregar(EntradaHistorial entrada) {
    if (_cargando || _entradas.any((e) => e.id == entrada.id)) return;
    if (!entrada.cumpleFiltros(usuarioId: _usuarioId, claseId: _claseId)) return;
    setState(() => _entradas = [entrada, ..._entradas]);
  }

  Future<void> _cargarAnteriores() async {
    setState(() => _cargandoMas = true);
    try {
      final mas = await _servicio.listar(
        widget.proyectoId,
        usuarioId: _usuarioId,
        claseId: _claseId,
        antesDe: _entradas.last.id,
      );
      if (!mounted) return;
      setState(() {
        _entradas = [..._entradas, ...mas];
        _hayAnteriores = mas.length == HistorialService.limite;
      });
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.mensaje)));
      }
    } finally {
      if (mounted) setState(() => _cargandoMas = false);
    }
  }

  void _cambiarFiltros({int? usuarioId, String? claseId, bool limpiarUsuario = false, bool limpiarClase = false}) {
    setState(() {
      if (limpiarUsuario) _usuarioId = null;
      if (limpiarClase) _claseId = null;
      _usuarioId = usuarioId ?? _usuarioId;
      _claseId = claseId ?? _claseId;
    });
    recargar();
  }

  Set<String> get _idsVigentes => {for (final c in widget.diagrama?.clases ?? <ClaseUml>[]) c.id};

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _filtros(),
        Expanded(
          child: RefreshIndicator(
            color: AppColors.primario,
            backgroundColor: AppColors.tarjeta,
            onRefresh: recargar,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(8, 12, 8, 24),
              children: _lista(),
            ),
          ),
        ),
      ],
    );
  }

  List<Widget> _lista() {
    if (_error != null && _entradas.isEmpty) {
      return [
        Padding(
          padding: const EdgeInsets.all(8),
          child: MensajeError(
            _error!.sinConexion
                ? 'No es posible cargar el historial. Revisá tu conexión a internet.'
                : _error!.mensaje,
            icono: _error!.sinConexion ? Icons.wifi_off : Icons.error_outline,
          ),
        ),
        Center(child: _BotonSecundario(texto: 'Reintentar', onTap: recargar)),
      ];
    }
    if (_cargando && _entradas.isEmpty) {
      return const [
        SizedBox(height: 60),
        Center(child: CircularProgressIndicator(color: AppColors.primario)),
      ];
    }
    if (_entradas.isEmpty) {
      final hayFiltros = _usuarioId != null || _claseId != null;
      return [
        _TextoVacio(hayFiltros
            ? 'No hay cambios con estos filtros.'
            : 'El historial está vacío. Los cambios que se hagan en el diagrama van a aparecer acá.'),
      ];
    }

    final vigentes = _idsVigentes;
    return [
      for (final e in _entradas)
        _Entrada(entrada: e, claseExiste: e.idElemento == null || vigentes.contains(e.idElemento)),
      if (_hayAnteriores)
        Center(
          child: Padding(
            padding: const EdgeInsets.only(top: 8),
            child: _BotonSecundario(
              texto: _cargandoMas ? 'Cargando…' : 'Cargar anteriores',
              onTap: _cargandoMas ? null : _cargarAnteriores,
            ),
          ),
        ),
    ];
  }

  Widget _filtros() {
    // Las clases del diagrama, con su nombre actual, más las que solo quedan en el historial.
    final vigentes = widget.diagrama?.clases ?? <ClaseUml>[];
    final idsVigentes = _idsVigentes;
    final clases = [
      for (final c in vigentes) (id: c.id, nombre: c.nombre),
      for (final c in _opciones.clases)
        if (!idsVigentes.contains(c.id)) (id: c.id, nombre: '${c.nombre} (eliminada)'),
    ]..sort((a, b) => a.nombre.toLowerCase().compareTo(b.nombre.toLowerCase()));

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: AppColors.borde))),
      child: Row(
        children: [
          Expanded(
            child: _Selector<int>(
              valor: _usuarioId,
              textoTodos: 'Todos los integrantes',
              opciones: [for (final i in _opciones.integrantes) (valor: i.id, texto: i.nombre)],
              onCambiar: (v) => v == null
                  ? _cambiarFiltros(limpiarUsuario: true)
                  : _cambiarFiltros(usuarioId: v),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _Selector<String>(
              valor: _claseId,
              textoTodos: 'Todas las clases',
              opciones: [for (final c in clases) (valor: c.id, texto: c.nombre)],
              onCambiar: (v) =>
                  v == null ? _cambiarFiltros(limpiarClase: true) : _cambiarFiltros(claseId: v),
            ),
          ),
        ],
      ),
    );
  }
}

class _Selector<T> extends StatelessWidget {
  final T? valor;
  final String textoTodos;
  final List<({T valor, String texto})> opciones;
  final ValueChanged<T?> onCambiar;

  const _Selector({
    required this.valor,
    required this.textoTodos,
    required this.opciones,
    required this.onCambiar,
  });

  @override
  Widget build(BuildContext context) {
    // Si el valor elegido ya no está entre las opciones, se muestra "Todos".
    final valorValido = opciones.any((o) => o.valor == valor) ? valor : null;
    return Container(
      height: 36,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: AppColors.tarjeta,
        border: Border.all(color: AppColors.borde),
        borderRadius: BorderRadius.circular(10),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<T?>(
          value: valorValido,
          isExpanded: true,
          dropdownColor: AppColors.tarjeta,
          iconEnabledColor: AppColors.texto3,
          style: const TextStyle(fontSize: 13, color: AppColors.texto2),
          items: [
            DropdownMenuItem<T?>(value: null, child: Text(textoTodos, overflow: TextOverflow.ellipsis)),
            for (final o in opciones)
              DropdownMenuItem<T?>(value: o.valor, child: Text(o.texto, overflow: TextOverflow.ellipsis)),
          ],
          onChanged: onCambiar,
        ),
      ),
    );
  }
}

class _Entrada extends StatelessWidget {
  final EntradaHistorial entrada;
  final bool claseExiste;

  const _Entrada({required this.entrada, required this.claseExiste});

  @override
  Widget build(BuildContext context) {
    final e = entrada;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          e.porAgente
              ? const AvatarAgente()
              : AvatarInicial(nombre: e.autorNombre, color: e.autorColor),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text.rich(
                  TextSpan(children: [
                    TextSpan(
                      text: e.porAgente ? 'Agente IA' : e.autorNombre,
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: e.porAgente ? AppColors.ia : AppColors.texto,
                      ),
                    ),
                    TextSpan(text: ' ${e.resumen}'),
                  ]),
                  style: const TextStyle(fontSize: 13, height: 1.45, color: AppColors.texto2),
                ),
                if (e.porAgente) ...[
                  const SizedBox(height: 4),
                  Text('a pedido de ${e.autorNombre}',
                      style: const TextStyle(fontSize: 12, color: AppColors.ia)),
                ],
                const SizedBox(height: 4),
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    if (e.nombreElemento != null && e.nombreElemento!.isNotEmpty)
                      Container(
                        constraints: const BoxConstraints(maxWidth: 180),
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                        decoration: BoxDecoration(
                          border: Border.all(color: AppColors.borde),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          e.nombreElemento!,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 12,
                            color: claseExiste ? AppColors.texto2 : AppColors.texto3,
                            decoration: claseExiste ? null : TextDecoration.lineThrough,
                            decorationColor: AppColors.texto3,
                          ),
                        ),
                      ),
                    Text(fechaRelativa(e.createdAt),
                        style: const TextStyle(fontSize: 12, color: AppColors.texto3)),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Avatar del agente de IA (círculo con destellos, colores --ia-*).
class AvatarAgente extends StatelessWidget {
  const AvatarAgente({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 30,
      height: 30,
      decoration: BoxDecoration(
        color: AppColors.iaBg,
        shape: BoxShape.circle,
        border: Border.all(color: AppColors.iaBorde),
      ),
      child: const Icon(Icons.auto_awesome, size: 15, color: AppColors.ia),
    );
  }
}

/// Círculo de color con la inicial del integrante.
class AvatarInicial extends StatelessWidget {
  final String? nombre;
  final Color color;

  const AvatarInicial({super.key, required this.nombre, required this.color});

  @override
  Widget build(BuildContext context) {
    final inicial = (nombre ?? '').trim().isEmpty ? '?' : nombre!.trim()[0].toUpperCase();
    return Container(
      width: 30,
      height: 30,
      alignment: Alignment.center,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      child: Text(inicial,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.fondo)),
    );
  }
}

class _TextoVacio extends StatelessWidget {
  final String texto;

  const _TextoVacio(this.texto);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 60, 16, 0),
      child: Text(texto,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 14, height: 1.5, color: AppColors.texto3)),
    );
  }
}

/// Botón chico gris (`.botonSecundario` de la web).
class _BotonSecundario extends StatelessWidget {
  final String texto;
  final VoidCallback? onTap;

  const _BotonSecundario({required this.texto, required this.onTap});

  @override
  Widget build(BuildContext context) {
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
