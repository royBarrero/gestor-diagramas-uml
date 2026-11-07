import 'package:flutter/material.dart';

import '../models/proyecto.dart';
import '../theme/app_theme.dart';
import '../utils/fecha_relativa.dart';
import 'avatar_usuario.dart';

const _maxAvatares = 4;

/// Tarjeta de proyecto, versión solo lectura de ProyectoCard.jsx (sin menú
/// de editar/miembros/eliminar ni generación de código).
class ProyectoCard extends StatelessWidget {
  final Proyecto proyecto;
  final VoidCallback onAbrir;

  const ProyectoCard({super.key, required this.proyecto, required this.onAbrir});

  @override
  Widget build(BuildContext context) {
    final esAdmin = proyecto.esAdministrador;
    final avatares = proyecto.miembros.take(_maxAvatares).toList();
    final restantes = proyecto.miembros.length - avatares.length;
    final tieneDescripcion = (proyecto.descripcion ?? '').trim().isNotEmpty;

    return Material(
      color: AppColors.tarjeta,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: AppColors.borde),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onAbrir,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _EtiquetaRol(esAdmin: esAdmin),
              const SizedBox(height: 14),
              Text(proyecto.nombre, style: AppTheme.heading(size: 20, weight: FontWeight.w600)),
              const SizedBox(height: 6),
              Text(
                tieneDescripcion ? proyecto.descripcion!.trim() : 'Sin descripción',
                style: TextStyle(
                  fontSize: 15,
                  height: 1.5,
                  color: tieneDescripcion ? AppColors.texto2 : AppColors.texto3,
                  fontStyle: tieneDescripcion ? FontStyle.normal : FontStyle.italic,
                ),
              ),
              const SizedBox(height: 18),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '${proyecto.totalClases} clase${proyecto.totalClases == 1 ? '' : 's'} · '
                      '${proyecto.totalRelaciones} relaci${proyecto.totalRelaciones == 1 ? 'ón' : 'ones'}',
                      style: const TextStyle(fontSize: 15, color: AppColors.texto2),
                    ),
                  ),
                  _Avatares(avatares: avatares, restantes: restantes),
                ],
              ),
              const SizedBox(height: 16),
              const Divider(height: 1, color: AppColors.borde),
              const SizedBox(height: 16),
              Text(fechaRelativa(proyecto.updatedAt),
                  style: const TextStyle(fontSize: 15, color: AppColors.texto3)),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: onAbrir,
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(42),
                  textStyle: AppTheme.heading(size: 14, weight: FontWeight.w600),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [Text('Ver proyecto'), SizedBox(width: 8), Icon(Icons.arrow_forward, size: 16)],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _EtiquetaRol extends StatelessWidget {
  final bool esAdmin;

  const _EtiquetaRol({required this.esAdmin});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: esAdmin ? AppColors.rolAdminBg : AppColors.rolColabBg,
        borderRadius: BorderRadius.circular(5),
      ),
      child: Text(
        esAdmin ? 'Administrador' : 'Colaborador',
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: esAdmin ? AppColors.rolAdminFg : AppColors.rolColabFg,
        ),
      ),
    );
  }
}

/// Avatares superpuestos (margin-left: -8px en la web).
class _Avatares extends StatelessWidget {
  final List<MiembroResumen> avatares;
  final int restantes;

  const _Avatares({required this.avatares, required this.restantes});

  @override
  Widget build(BuildContext context) {
    final circulos = <Widget>[
      for (final m in avatares) AvatarUsuario(id: m.id, nombre: m.nombre),
      if (restantes > 0) AvatarMas(restantes),
    ];
    if (circulos.isEmpty) return const SizedBox.shrink();

    return SizedBox(
      height: 32,
      width: 32 + (circulos.length - 1) * 24,
      child: Stack(
        children: [
          for (var i = 0; i < circulos.length; i++) Positioned(left: i * 24.0, child: circulos[i]),
        ],
      ),
    );
  }
}
