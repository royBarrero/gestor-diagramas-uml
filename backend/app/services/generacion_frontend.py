"""CU12: genera una app Flutter (Dart, `package:http`, sin manejo de estado
externo) a partir del mismo modelo estructural que ya usa `generacion_backend.py`
(`modelo_backend.construir_modelo_backend`) — listados y formularios CRUD por
entidad, apuntando a los endpoints `/api/...` que genera CU11.

Simplificaciones documentadas (acordadas con el usuario):
- Los campos de relación (`@ManyToOne`/`@OneToOne` dueño) se muestran en el
  formulario como un `DropdownButtonFormField` que trae la lista real de la
  entidad relacionada (vía su `*_service.dart`) y deja elegir un registro
  legible en vez de escribir un id a mano. El modelo Dart lo expone como un
  `int?` plano (`personaId`), y así viaja también en el JSON (`{"personaId": 3}`)
  — coincide con el DTO plano que expone el backend generado (`_campo_dto_relacion`
  en `generacion_backend.py`, no un objeto anidado).
- Las relaciones colección (`oneToMany`/`manyToMany`) no aparecen ni en el
  modelo Dart ni en las pantallas: además de ser más simple, el lado inverso
  (`mappedBy`) ahora se serializa con `@JsonIgnore` en el backend (ver fix en
  `generacion_backend.py`) para cortar el ciclo bidireccional con Jackson, así
  que en muchos casos ni siquiera viajan en el JSON.
"""

import io
import re
import zipfile
from pathlib import Path

from app.services.exportacion_diagrama import nombre_archivo_descarga
from app.services.modelo_backend import (
    EntidadModelo,
    ModeloBackend,
    RelacionModelo,
    construir_modelo_backend,
    todos_los_campos,
)

__all__ = ["generar_zip_frontend", "nombre_zip_frontend"]

# Plantilla base real (`flutter create --platforms=android,web`), versionada
# en el repo. Trae toda la estructura de proyecto (android/, web/, pubspec.yaml,
# .gitignore, analysis_options.yaml, etc.) que hoy no se generaba a mano.
_PLANTILLA_DIR = Path(__file__).resolve().parent.parent / "templates" / "flutter_base"

# Combinaciones color+ícono para las tarjetas del dashboard, asignadas por
# rotación (nunca al azar, para que la generación sea determinista).
_PALETA_TARJETAS = [
    ("Colors.blue", "Icons.people"),
    ("Colors.green", "Icons.shopping_cart"),
    ("Colors.orange", "Icons.inventory_2"),
    ("Colors.purple", "Icons.list_alt"),
    ("Colors.teal", "Icons.category"),
    ("Colors.pink", "Icons.business"),
    ("Colors.indigo", "Icons.description"),
    ("Colors.brown", "Icons.folder"),
]

_TIPO_JAVA_A_DART = {
    "String": "String",
    "int": "int",
    "long": "int",
    "Long": "int",
    "double": "double",
    "float": "double",
    "boolean": "bool",
    "char": "String",
    "LocalDate": "DateTime",
    "List<String>": "List<String>",
}


# CU14: modo offline (solo Android — sqflite no corre en Web sin paquetes
# adicionales). Estos tres archivos son genéricos: no dependen de qué
# entidades tenga el diagrama, así que se generan siempre igual, como
# plantillas fijas. Lo único que varía por diagrama es `registro_sync.dart`
# (generado por `_renderizar_registro_sync`) y, si hay entidad candidata a
# voz, `{entidad}_comando_voz.dart` (generado por `_renderizar_parser_voz`).

_LOCAL_DB_DART = """import 'dart:convert';
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

class OperacionPendiente {
  final int id;
  final String entidad;
  final String operacion;
  final int? entidadId;
  final Map<String, dynamic> payload;
  final Map<String, dynamic>? snapshotPrevio;

  OperacionPendiente({
    required this.id,
    required this.entidad,
    required this.operacion,
    required this.entidadId,
    required this.payload,
    required this.snapshotPrevio,
  });

  factory OperacionPendiente.fromRow(Map<String, dynamic> fila) {
    return OperacionPendiente(
      id: fila['id'] as int,
      entidad: fila['entidad'] as String,
      operacion: fila['operacion'] as String,
      entidadId: fila['entidad_id'] as int?,
      payload: jsonDecode(fila['payload'] as String) as Map<String, dynamic>,
      snapshotPrevio: fila['snapshot_previo'] != null
          ? jsonDecode(fila['snapshot_previo'] as String) as Map<String, dynamic>
          : null,
    );
  }
}

class ConflictoPendiente {
  final int id;
  final String entidad;
  final int entidadId;
  final Map<String, dynamic> payloadLocal;
  final Map<String, dynamic> payloadServidor;

  ConflictoPendiente({
    required this.id,
    required this.entidad,
    required this.entidadId,
    required this.payloadLocal,
    required this.payloadServidor,
  });

  factory ConflictoPendiente.fromRow(Map<String, dynamic> fila) {
    return ConflictoPendiente(
      id: fila['id'] as int,
      entidad: fila['entidad'] as String,
      entidadId: fila['entidad_id'] as int,
      payloadLocal: jsonDecode(fila['payload_local'] as String) as Map<String, dynamic>,
      payloadServidor: jsonDecode(fila['payload_servidor'] as String) as Map<String, dynamic>,
    );
  }
}

/// Persistencia local (modo offline, CU14). Una única tabla genérica
/// `cache_local` guarda el último JSON conocido de cada registro de cada
/// entidad (para poder listar sin conexión), más una cola de operaciones
/// pendientes de sincronizar y una tabla de conflictos sin resolver.
class LocalDb {
  LocalDb._();
  static final LocalDb instancia = LocalDb._();
  Database? _db;

  Future<Database> get _database async {
    if (_db != null) return _db!;
    final directorio = await getDatabasesPath();
    final ruta = p.join(directorio, 'app_offline.db');
    _db = await openDatabase(
      ruta,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE cache_local (
            entidad TEXT NOT NULL,
            id INTEGER NOT NULL,
            data TEXT NOT NULL,
            PRIMARY KEY (entidad, id)
          )
        ''');
        await db.execute('''
          CREATE TABLE cola_sincronizacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entidad TEXT NOT NULL,
            operacion TEXT NOT NULL,
            entidad_id INTEGER,
            payload TEXT NOT NULL,
            snapshot_previo TEXT,
            creado_en TEXT NOT NULL,
            sincronizado INTEGER NOT NULL DEFAULT 0
          )
        ''');
        await db.execute('''
          CREATE TABLE conflictos_pendientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entidad TEXT NOT NULL,
            entidad_id INTEGER NOT NULL,
            payload_local TEXT NOT NULL,
            payload_servidor TEXT NOT NULL,
            creado_en TEXT NOT NULL,
            resuelto INTEGER NOT NULL DEFAULT 0
          )
        ''');
      },
    );
    return _db!;
  }

  Future<void> guardarCache(String entidad, int id, Map<String, dynamic> data) async {
    final db = await _database;
    await db.insert(
      'cache_local',
      {'entidad': entidad, 'id': id, 'data': jsonEncode(data)},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<List<Map<String, dynamic>>> listarCache(String entidad) async {
    final db = await _database;
    final filas = await db.query('cache_local', where: 'entidad = ?', whereArgs: [entidad]);
    return filas.map((f) => jsonDecode(f['data'] as String) as Map<String, dynamic>).toList();
  }

  Future<void> encolar({
    required String entidad,
    required String operacion,
    int? entidadId,
    required Map<String, dynamic> payload,
    Map<String, dynamic>? snapshotPrevio,
  }) async {
    final db = await _database;
    await db.insert('cola_sincronizacion', {
      'entidad': entidad,
      'operacion': operacion,
      'entidad_id': entidadId,
      'payload': jsonEncode(payload),
      'snapshot_previo': snapshotPrevio != null ? jsonEncode(snapshotPrevio) : null,
      'creado_en': DateTime.now().toIso8601String(),
      'sincronizado': 0,
    });
  }

  Future<List<OperacionPendiente>> listarPendientes() async {
    final db = await _database;
    final filas = await db.query('cola_sincronizacion', where: 'sincronizado = 0', orderBy: 'id ASC');
    return filas.map(OperacionPendiente.fromRow).toList();
  }

  Future<int> contarPendientes(String entidad) async {
    final db = await _database;
    final resultado = await db.rawQuery(
      'SELECT COUNT(*) as total FROM cola_sincronizacion WHERE sincronizado = 0 AND entidad = ?',
      [entidad],
    );
    return Sqflite.firstIntValue(resultado) ?? 0;
  }

  Future<void> marcarSincronizado(int idOperacion) async {
    final db = await _database;
    await db.update('cola_sincronizacion', {'sincronizado': 1}, where: 'id = ?', whereArgs: [idOperacion]);
  }

  Future<void> registrarConflicto({
    required String entidad,
    required int entidadId,
    required Map<String, dynamic> payloadLocal,
    required Map<String, dynamic> payloadServidor,
  }) async {
    final db = await _database;
    await db.insert('conflictos_pendientes', {
      'entidad': entidad,
      'entidad_id': entidadId,
      'payload_local': jsonEncode(payloadLocal),
      'payload_servidor': jsonEncode(payloadServidor),
      'creado_en': DateTime.now().toIso8601String(),
      'resuelto': 0,
    });
  }

  Future<List<ConflictoPendiente>> listarConflictos(String entidad) async {
    final db = await _database;
    final filas = await db.query(
      'conflictos_pendientes',
      where: 'entidad = ? AND resuelto = 0',
      whereArgs: [entidad],
    );
    return filas.map(ConflictoPendiente.fromRow).toList();
  }

  Future<void> resolverConflicto(int idConflicto) async {
    final db = await _database;
    await db.update('conflictos_pendientes', {'resuelto': 1}, where: 'id = ?', whereArgs: [idConflicto]);
  }
}
"""

_SYNC_SERVICE_DART = """import 'dart:convert';
import 'local_db.dart';

/// Funciones que sabe cómo hablar con el backend real para una entidad
/// puntual, reutilizando su `*_service.dart` ya generado. `registro_sync.dart`
/// las registra una por entidad al arrancar la app.
class EntidadSyncHandlers {
  final Future<Map<String, dynamic>> Function(Map<String, dynamic> payload) crear;
  final Future<Map<String, dynamic>> Function(int id, Map<String, dynamic> payload) actualizar;
  final Future<void> Function(int id) eliminar;
  final Future<Map<String, dynamic>> Function(int id) obtener;

  EntidadSyncHandlers({
    required this.crear,
    required this.actualizar,
    required this.eliminar,
    required this.obtener,
  });
}

/// Modo offline (CU14): toda escritura (crear/editar/eliminar) se guarda
/// primero en la cola local y recién después se intenta sincronizar contra
/// el backend. Si no hay conexión, la operación queda pendiente y se
/// reintenta la próxima vez que se llama a `flush()` (al reconectar, o al
/// volver a entrar a una pantalla de lista).
class SyncService {
  SyncService._();
  static final SyncService instancia = SyncService._();

  final Map<String, EntidadSyncHandlers> _handlers = {};

  void registrar(String entidad, EntidadSyncHandlers handlers) {
    _handlers[entidad] = handlers;
  }

  EntidadSyncHandlers? handlersDe(String entidad) => _handlers[entidad];

  Future<void> crear(String entidad, Map<String, dynamic> payload) async {
    await LocalDb.instancia.encolar(entidad: entidad, operacion: 'crear', payload: payload);
    await flush();
  }

  Future<void> actualizar(
    String entidad,
    int id,
    Map<String, dynamic> payload,
    Map<String, dynamic> snapshotPrevio,
  ) async {
    await LocalDb.instancia.encolar(
      entidad: entidad,
      operacion: 'editar',
      entidadId: id,
      payload: payload,
      snapshotPrevio: snapshotPrevio,
    );
    await flush();
  }

  Future<void> eliminar(String entidad, int id) async {
    await LocalDb.instancia.encolar(entidad: entidad, operacion: 'eliminar', entidadId: id, payload: {});
    await flush();
  }

  Future<int> contarPendientes(String entidad) => LocalDb.instancia.contarPendientes(entidad);

  /// Procesa la cola de pendientes. Si una operación falla (ej. sin
  /// conexión) queda pendiente para el próximo intento. No hay backoff ni
  /// manejo de dependencias entre operaciones encadenadas — alcanza para
  /// una demo, no es una cola de producción.
  Future<void> flush() async {
    final pendientes = await LocalDb.instancia.listarPendientes();
    for (final op in pendientes) {
      final handlers = _handlers[op.entidad];
      if (handlers == null) continue;
      try {
        if (op.operacion == 'crear') {
          await handlers.crear(op.payload);
        } else if (op.operacion == 'editar') {
          if (op.snapshotPrevio != null && op.entidadId != null) {
            final actual = await handlers.obtener(op.entidadId!);
            if (jsonEncode(actual) != jsonEncode(op.snapshotPrevio)) {
              // El servidor cambió desde que el dispositivo editó offline:
              // se guarda como conflicto para que el usuario elija, no se
              // sobreescribe sin preguntar.
              await LocalDb.instancia.registrarConflicto(
                entidad: op.entidad,
                entidadId: op.entidadId!,
                payloadLocal: op.payload,
                payloadServidor: actual,
              );
              await LocalDb.instancia.marcarSincronizado(op.id);
              continue;
            }
          }
          await handlers.actualizar(op.entidadId!, op.payload);
        } else if (op.operacion == 'eliminar') {
          await handlers.eliminar(op.entidadId!);
        }
        await LocalDb.instancia.marcarSincronizado(op.id);
      } catch (_) {
        // Sigue pendiente; se reintenta en el próximo flush().
      }
    }
  }
}
"""

_CONNECTIVITY_BANNER_DART = """import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'sync_service.dart';

/// Banner "Sin conexión. N cambios pendientes de sincronizar." — aparece en
/// cualquier pantalla de lista cuando corresponde (sin conexión, o con
/// operaciones todavía sin sincronizar).
class ConnectivityBanner extends StatefulWidget {
  final String entidad;
  const ConnectivityBanner({super.key, required this.entidad});

  @override
  State<ConnectivityBanner> createState() => _ConnectivityBannerState();
}

class _ConnectivityBannerState extends State<ConnectivityBanner> {
  bool _sinConexion = false;
  int _pendientes = 0;
  StreamSubscription<List<ConnectivityResult>>? _suscripcion;

  @override
  void initState() {
    super.initState();
    _verificar();
    _suscripcion = Connectivity().onConnectivityChanged.listen((_) async {
      await SyncService.instancia.flush();
      _verificar();
    });
  }

  Future<void> _verificar() async {
    final estado = await Connectivity().checkConnectivity();
    final sinConexion = estado.every((r) => r == ConnectivityResult.none);
    final pendientes = await SyncService.instancia.contarPendientes(widget.entidad);
    if (mounted) {
      setState(() {
        _sinConexion = sinConexion;
        _pendientes = pendientes;
      });
    }
  }

  @override
  void dispose() {
    _suscripcion?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_sinConexion && _pendientes == 0) return const SizedBox.shrink();
    final mensaje = _sinConexion
        ? 'Sin conexión. $_pendientes cambios pendientes de sincronizar.'
        : '$_pendientes cambios pendientes de sincronizar.';
    return Container(
      width: double.infinity,
      color: Colors.amber.shade100,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Text(mensaje, textAlign: TextAlign.center),
    );
  }
}
"""

_CONFLICT_DIALOG_DART = """import 'package:flutter/material.dart';
import 'local_db.dart';
import 'sync_service.dart';

/// Muestra, uno por uno, los conflictos de sincronización sin resolver de
/// `entidad` (ver `SyncService.flush`): la versión que quedó guardada
/// localmente contra la que devolvió el servidor, y deja al usuario elegir
/// cuál conservar antes de seguir.
Future<void> mostrarConflictosPendientes(BuildContext context, String entidad, VoidCallback alResolver) async {
  final conflictos = await LocalDb.instancia.listarConflictos(entidad);
  for (final conflicto in conflictos) {
    if (!context.mounted) return;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Conflicto de sincronización'),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Este registro cambió en el servidor mientras se editaba sin conexión.'),
              const SizedBox(height: 12),
              const Text('Versión local (sin sincronizar):', style: TextStyle(fontWeight: FontWeight.bold)),
              ..._camposComoTexto(conflicto.payloadLocal),
              const SizedBox(height: 12),
              const Text('Versión del servidor:', style: TextStyle(fontWeight: FontWeight.bold)),
              ..._camposComoTexto(conflicto.payloadServidor),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () async {
              final handlers = SyncService.instancia.handlersDe(entidad);
              if (handlers != null) {
                await handlers.actualizar(conflicto.entidadId, conflicto.payloadLocal);
              }
              await LocalDb.instancia.resolverConflicto(conflicto.id);
              if (dialogContext.mounted) Navigator.pop(dialogContext);
              alResolver();
            },
            child: const Text('Usar versión local'),
          ),
          TextButton(
            onPressed: () async {
              await LocalDb.instancia.resolverConflicto(conflicto.id);
              if (dialogContext.mounted) Navigator.pop(dialogContext);
              alResolver();
            },
            child: const Text('Usar versión del servidor'),
          ),
        ],
      ),
    );
  }
}

List<Widget> _camposComoTexto(Map<String, dynamic> payload) {
  return payload.entries
      .where((e) => e.key != 'id')
      .map((e) => Text('${e.key}: ${e.value}'))
      .toList();
}
"""


def nombre_zip_frontend(nombre_proyecto: str) -> str:
    return nombre_archivo_descarga(f"{nombre_proyecto} frontend", "zip")


def _tipo_dart(tipo_java: str) -> str:
    return _TIPO_JAVA_A_DART.get(tipo_java, "String")


def _capitalizar(texto: str) -> str:
    return texto[:1].upper() + texto[1:] if texto else texto


def _snake(nombre_java: str) -> str:
    """PascalCase/camelCase -> snake_case, para nombres de archivo Dart."""
    resultado = []
    for i, c in enumerate(nombre_java):
        if c.isupper() and i > 0:
            resultado.append("_")
        resultado.append(c.lower())
    return "".join(resultado)


def _relaciones_incluidas(entidad: EntidadModelo) -> list[RelacionModelo]:
    # Solo relaciones singulares del lado dueño: son las únicas que el
    # backend generado serializa de forma simple (objeto anidado con id).
    return [r for r in entidad.relaciones if r.propietaria and not r.es_coleccion]


class _Campo:
    """Representación unificada de un campo de formulario/modelo Dart,
    ya sea un atributo (`CampoModelo`) o una relación singular (`RelacionModelo`)."""

    def __init__(
        self, nombre: str, tipo_dart: str, es_relacion: bool = False, entidad_relacionada: str | None = None
    ):
        self.nombre = nombre
        self.tipo_dart = tipo_dart
        self.es_relacion = es_relacion
        self.entidad_relacionada = entidad_relacionada  # nombre_java del otro lado, sólo si es_relacion


def _campos_dart(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> list[_Campo]:
    campos = [_Campo(c.nombre, _tipo_dart(c.tipo_java)) for c in todos_los_campos(entidad, entidades_por_nombre)]
    campos += [
        _Campo(f"{r.nombre}Id", "int", es_relacion=True, entidad_relacionada=r.entidad_relacionada)
        for r in _relaciones_incluidas(entidad)
    ]
    return campos


def _entidad_candidata_voz(modelo: ModeloBackend, entidades_por_nombre: dict[str, EntidadModelo]):
    """CU14 (B.1): elige la entidad "principal para voz" entre `modelo.entidades`,
    la que cumpla la MAYORÍA de tres criterios: tiene un atributo de fecha,
    tiene 2+ relaciones hacia otras entidades, y no es superclase de herencia.
    "Mayoría" de 3 criterios = al menos 2 (no alcanza con cumplir solo uno,
    ej. "no ser superclase" es trivialmente cierto para casi cualquier
    entidad y no debería bastar por sí solo). Empate -> más atributos
    propios. Si ninguna entidad llega a 2 criterios, no hay candidata y CU14
    no genera nada de voz (el resto del modo offline se genera igual)."""
    UMBRAL_MAYORIA = 2
    mejor, mejor_puntaje, mejor_cantidad_campos = None, UMBRAL_MAYORIA - 1, -1
    for entidad in modelo.entidades:
        campos = todos_los_campos(entidad, entidades_por_nombre)
        tiene_fecha = any(c.tipo_java == "LocalDate" for c in campos)
        relaciones_externas = [r for r in entidad.relaciones if r.entidad_relacionada != entidad.nombre_java]
        tiene_dos_relaciones = len(relaciones_externas) >= 2
        no_es_superclase = not entidad.tiene_subclases
        puntaje = int(tiene_fecha) + int(tiene_dos_relaciones) + int(no_es_superclase)
        if puntaje < UMBRAL_MAYORIA:
            continue
        if puntaje > mejor_puntaje or (puntaje == mejor_puntaje and len(entidad.campos) > mejor_cantidad_campos):
            mejor, mejor_puntaje, mejor_cantidad_campos = entidad, puntaje, len(entidad.campos)
    return mejor


def _renderizar_modelo(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> str:
    tipo_id_dart = _tipo_dart(entidad.campo_id_tipo)
    campos = _campos_dart(entidad, entidades_por_nombre)

    props = [f"  {c.tipo_dart}? {c.nombre};" for c in campos]

    # El campo de relación (`{rel.nombre}Id`) viaja plano en el JSON, igual
    # que cualquier otro `int` — coincide con el DTO del backend generado
    # (`_campo_dto_relacion` en generacion_backend.py), que también es plano.
    lineas_from_json = []
    for c in campos:
        if c.tipo_dart == "DateTime":
            lineas_from_json.append(f"      {c.nombre}: json['{c.nombre}'] != null ? DateTime.tryParse(json['{c.nombre}']) : null,")
        elif c.tipo_dart == "List<String>":
            lineas_from_json.append(f"      {c.nombre}: json['{c.nombre}'] != null ? List<String>.from(json['{c.nombre}']) : null,")
        else:
            lineas_from_json.append(f"      {c.nombre}: json['{c.nombre}'],")

    lineas_to_json = []
    for c in campos:
        if c.tipo_dart == "DateTime":
            lineas_to_json.append(f"      '{c.nombre}': {c.nombre}?.toIso8601String().split('T').first,")
        else:
            lineas_to_json.append(f"      '{c.nombre}': {c.nombre},")

    return f"""class {entidad.nombre_java} {{
  {tipo_id_dart}? id;
{chr(10).join(props)}

  {entidad.nombre_java}({{
    this.id,
{chr(10).join(f"    this.{c.nombre}," for c in campos)}
  }});

  factory {entidad.nombre_java}.fromJson(Map<String, dynamic> json) {{
    return {entidad.nombre_java}(
      id: json['id'],
{chr(10).join(lineas_from_json)}
    );
  }}

  Map<String, dynamic> toJson() {{
    return {{
      'id': id,
{chr(10).join(lineas_to_json)}
    }};
  }}
}}
"""


def _renderizar_service(entidad: EntidadModelo) -> str:
    archivo_modelo = _snake(entidad.nombre_java)
    tipo_id_dart = _tipo_dart(entidad.campo_id_tipo)
    clase = entidad.nombre_java
    endpoint = entidad.endpoint
    return f"""import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/{archivo_modelo}.dart';
import 'api_config.dart';

class {clase}Service {{
  Future<List<{clase}>> listar() async {{
    final respuesta = await http.get(Uri.parse('$baseUrl/{endpoint}'));
    final datos = jsonDecode(respuesta.body) as List;
    return datos.map((e) => {clase}.fromJson(e)).toList();
  }}

  Future<{clase}> obtenerPorId({tipo_id_dart} id) async {{
    final respuesta = await http.get(Uri.parse('$baseUrl/{endpoint}/$id'));
    return {clase}.fromJson(jsonDecode(respuesta.body));
  }}

  Future<{clase}> crear({clase} entidad) async {{
    final respuesta = await http.post(
      Uri.parse('$baseUrl/{endpoint}'),
      headers: {{'Content-Type': 'application/json'}},
      body: jsonEncode(entidad.toJson()),
    );
    return {clase}.fromJson(jsonDecode(respuesta.body));
  }}

  Future<{clase}> actualizar({tipo_id_dart} id, {clase} entidad) async {{
    final respuesta = await http.put(
      Uri.parse('$baseUrl/{endpoint}/$id'),
      headers: {{'Content-Type': 'application/json'}},
      body: jsonEncode(entidad.toJson()),
    );
    return {clase}.fromJson(jsonDecode(respuesta.body));
  }}

  Future<void> eliminar({tipo_id_dart} id) async {{
    await http.delete(Uri.parse('$baseUrl/{endpoint}/$id'));
  }}
}}
"""


def _renderizar_registro_sync(modelo: ModeloBackend) -> str:
    """`lib/local/registro_sync.dart`: registra, para cada entidad, cómo
    hablarle al backend real (reutilizando su `*_service.dart` ya generado)
    para que `SyncService` pueda sincronizar la cola sin un switch a mano."""
    imports = []
    registros = []
    for entidad in modelo.entidades:
        archivo = _snake(entidad.nombre_java)
        clase = entidad.nombre_java
        imports.append(f"import '../models/{archivo}.dart';")
        imports.append(f"import '../services/{archivo}_service.dart';")
        variable_service = f"servicio{clase}"
        registros.append(
            f"""  final {variable_service} = {clase}Service();
  SyncService.instancia.registrar(
    '{clase}',
    EntidadSyncHandlers(
      crear: (payload) async => (await {variable_service}.crear({clase}.fromJson(payload))).toJson(),
      actualizar: (id, payload) async =>
          (await {variable_service}.actualizar(id, {clase}.fromJson(payload))).toJson(),
      eliminar: (id) => {variable_service}.eliminar(id),
      obtener: (id) async => (await {variable_service}.obtenerPorId(id)).toJson(),
    ),
  );"""
        )
    imports_str = "\n".join(imports)
    registros_str = "\n\n".join(registros)
    return f"""{imports_str}
import 'sync_service.dart';

/// Registra, para cada entidad del diagrama, cómo hablarle al backend real
/// (usando su `*_service.dart` ya generado). Se llama una vez en `main()`.
void registrarHandlersSync() {{
{registros_str}
}}
"""


def _conversion_valor_voz(tipo_dart: str) -> str:
    if tipo_dart == "int":
        return "int.tryParse(valorTexto)"
    if tipo_dart == "double":
        return "double.tryParse(valorTexto)"
    if tipo_dart == "bool":
        return "(valorTexto.toLowerCase() == 'true' || valorTexto.toLowerCase() == 'si' || valorTexto.toLowerCase() == 'sí')"
    if tipo_dart == "List<String>":
        return "valorTexto.split(',').map((s) => s.trim()).toList()"
    return "valorTexto"


def _renderizar_parser_voz(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> str:
    """CU14 (B.3): parser de reglas a medida (sin IA externa, solo matching de
    palabras clave y extracción simple de valores) para la entidad detectada
    en B.1 (`_entidad_candidata_voz`). Reconoce "crear ... con <atributo>
    <valor>...", "editar <atributo> de <id> a <valor>" y "eliminar <id>"."""
    archivo_modelo = _snake(entidad.nombre_java)
    clase = entidad.nombre_java
    nombre_hablado = entidad.nombre_original.lower()

    campos = todos_los_campos(entidad, entidades_por_nombre)
    campo_principal = _campo_titulo(entidad, entidades_por_nombre)

    lista_atributos_dart = ", ".join(f"'{c.nombre}'" for c in campos)
    casos_conversion = "\n".join(
        f"    case '{c.nombre}':\n      return {_conversion_valor_voz(_tipo_dart(c.tipo_java))};" for c in campos
    )

    if campo_principal is None:
        cuerpo_crear = (
            "    return ComandoNoReconocido(\n"
            "      'Esta entidad no tiene atributos, no se puede crear por voz.',\n"
            "    );"
        )
    else:
        cuerpo_crear = rf"""    var resto = texto.substring('crear'.length).trim();
    const prefijoEntidad = '{nombre_hablado}';
    if (resto.startsWith(prefijoEntidad)) {{
      resto = resto.substring(prefijoEntidad.length).trim();
    }}
    if (resto.isEmpty) {{
      return ComandoNoReconocido(
        'No entendí los datos. Decí, por ejemplo: "crear {nombre_hablado} ...".',
      );
    }}
    final partes = resto.split(RegExp(r'\s+con\s+'));
    final valores = <String, String>{{'{campo_principal.nombre}': partes.first.trim()}};
    for (final parte in partes.skip(1)) {{
      final match = RegExp(r'^(\w+)\s+(.+)$').firstMatch(parte.trim());
      if (match != null && _atributosVoz{clase}.contains(match.group(1))) {{
        valores[match.group(1)!] = match.group(2)!.trim();
      }}
    }}
    return ComandoCrear(valores);"""

    mensaje_ejemplo_editar = campo_principal.nombre if campo_principal is not None else "atributo"

    return rf"""import 'package:flutter/material.dart';
import '../models/{archivo_modelo}.dart';
import 'sync_service.dart';

/// Parser de reglas generado a medida para {entidad.nombre_original}: NO llama
/// a ningún servicio de IA externo, solo coincidencia de palabras clave y
/// extracción simple de valores. Limitación conocida: los nombres de
/// atributo se reconocen como una sola palabra hablada (ej. "estado"), no en
/// variantes con espacios para atributos de más de una palabra.

const List<String> _atributosVoz{clase} = [{lista_atributos_dart}];

sealed class ComandoVoz {{}}

class ComandoCrear extends ComandoVoz {{
  final Map<String, String> valores;
  ComandoCrear(this.valores);
}}

class ComandoEditar extends ComandoVoz {{
  final int id;
  final String atributo;
  final String valor;
  ComandoEditar(this.id, this.atributo, this.valor);
}}

class ComandoEliminar extends ComandoVoz {{
  final int id;
  ComandoEliminar(this.id);
}}

class ComandoNoReconocido extends ComandoVoz {{
  final String motivo;
  ComandoNoReconocido(this.motivo);
}}

ComandoVoz interpretarComando{clase}(String textoOriginal) {{
  final texto = textoOriginal.trim().toLowerCase();

  if (texto.startsWith('eliminar')) {{
    final match = RegExp(r'(\d+)').firstMatch(texto);
    if (match == null) {{
      return ComandoNoReconocido(
        'No entendí qué registro eliminar. Decí, por ejemplo: "eliminar {nombre_hablado} 5".',
      );
    }}
    return ComandoEliminar(int.parse(match.group(1)!));
  }}

  if (texto.startsWith('editar')) {{
    final match = RegExp(r'^editar\s+(\w+)\s+de\s+(\d+)\s+a\s+(.+)$').firstMatch(texto);
    if (match == null) {{
      return ComandoNoReconocido(
        'No entendí. Decí, por ejemplo: "editar {mensaje_ejemplo_editar} de 5 a nuevo valor".',
      );
    }}
    final atributo = match.group(1)!;
    if (!_atributosVoz{clase}.contains(atributo)) {{
      return ComandoNoReconocido(
        'No reconozco el atributo "$atributo". Atributos disponibles: ${{_atributosVoz{clase}.join(', ')}}.',
      );
    }}
    return ComandoEditar(int.parse(match.group(2)!), atributo, match.group(3)!.trim());
  }}

  if (texto.startsWith('crear')) {{
{cuerpo_crear}
  }}

  return ComandoNoReconocido('No reconocí ningún comando. Empezá con "crear", "editar" o "eliminar".');
}}

dynamic _convertirValor{clase}(String atributo, String valorTexto) {{
  switch (atributo) {{
{casos_conversion}
    default:
      return valorTexto;
  }}
}}

Future<void> ejecutarComando{clase}(
  BuildContext context,
  ComandoVoz comando,
  List<{clase}> itemsActuales,
  VoidCallback recargar,
) async {{
  if (comando is ComandoCrear) {{
    final payload = <String, dynamic>{{}};
    comando.valores.forEach((atributo, valorTexto) {{
      payload[atributo] = _convertirValor{clase}(atributo, valorTexto);
    }});
    await SyncService.instancia.crear('{clase}', payload);
    recargar();
  }} else if (comando is ComandoEditar) {{
    {clase}? objetivo;
    for (final item in itemsActuales) {{
      if (item.id == comando.id) {{
        objetivo = item;
        break;
      }}
    }}
    if (objetivo == null) {{
      if (context.mounted) {{
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No encontré ese registro en la lista actual.')),
        );
      }}
      return;
    }}
    final anterior = Map<String, dynamic>.from(objetivo.toJson());
    final payload = Map<String, dynamic>.from(objetivo.toJson());
    payload[comando.atributo] = _convertirValor{clase}(comando.atributo, comando.valor);
    await SyncService.instancia.actualizar('{clase}', comando.id, payload, anterior);
    recargar();
  }} else if (comando is ComandoEliminar) {{
    await SyncService.instancia.eliminar('{clase}', comando.id);
    recargar();
  }} else if (comando is ComandoNoReconocido) {{
    if (context.mounted) {{
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(comando.motivo)));
    }}
  }}
}}
"""


def _campo_texto(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]):
    """El primer atributo de texto (propio o heredado) de una entidad, o
    `None` si no tiene ninguno — a diferencia de `_campo_titulo`, acá no se
    cae a "el primer campo de cualquier tipo": se usa para las opciones del
    dropdown de relación, donde un id o una fecha como "etiqueta" no ayuda
    más que el fallback `"Entidad #id"`."""
    campos_texto = [c for c in todos_los_campos(entidad, entidades_por_nombre) if c.tipo_java in ("String", "char")]
    return campos_texto[0] if campos_texto else None


def _campo_titulo(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]):
    """El campo que se usa como título de cada item de la lista: el primer
    atributo de texto (propio o heredado), o el primero de cualquier tipo si
    no hay ninguno de texto. `None` si la entidad no tiene atributos."""
    campo_texto = _campo_texto(entidad, entidades_por_nombre)
    if campo_texto is not None:
        return campo_texto
    campos = todos_los_campos(entidad, entidades_por_nombre)
    return campos[0] if campos else None


def _etiqueta_legible(nombre_campo: str) -> str:
    """`fechaNacimiento` -> `Fecha Nacimiento` (para mostrar en la UI)."""
    con_espacios = re.sub(r"(?<!^)(?=[A-Z])", " ", nombre_campo)
    return _capitalizar(con_espacios)


def _valor_display_dart(nombre_campo: str, tipo_dart: str) -> str:
    """Expresión Dart (para interpolar en un string) que muestra el valor de
    `item.<nombre_campo>` de forma legible, sin agregar la dependencia `intl`."""
    acceso = f"item.{nombre_campo}"
    if tipo_dart == "DateTime":
        return f"({acceso} != null ? {acceso}!.toIso8601String().split('T').first : '')"
    if tipo_dart == "bool":
        return f"({acceso} == null ? '' : ({acceso}! ? 'Sí' : 'No'))"
    if tipo_dart == "List<String>":
        return f"({acceso} != null ? {acceso}!.join(', ') : '')"
    if tipo_dart in ("int", "double"):
        return f"({acceso}?.toString() ?? '')"
    return f"({acceso} ?? '')"


def _lineas_detalle_item(
    entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo], excluir
) -> list[str]:
    """Una línea `Text('Etiqueta: valor')` por cada atributo propio o
    heredado, salvo el que ya se usa como título de la tarjeta."""
    lineas = []
    for c in todos_los_campos(entidad, entidades_por_nombre):
        if excluir is not None and c.nombre == excluir.nombre:
            continue
        etiqueta = _etiqueta_legible(c.nombre)
        valor = _valor_display_dart(c.nombre, _tipo_dart(c.tipo_java))
        lineas.append(f"                      Text('{etiqueta}: ${{{valor}}}'),")
    return lineas


def _renderizar_list_screen(
    entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo], *, es_entidad_voz: bool = False
) -> str:
    archivo_modelo = _snake(entidad.nombre_java)
    clase = entidad.nombre_java

    campo_titulo = _campo_titulo(entidad, entidades_por_nombre)
    if campo_titulo is not None:
        # _valor_display_dart siempre da una expresión ya tipada String, así
        # que se usa directa (envolverla en '${...}' sería redundante).
        titulo_expr = _valor_display_dart(campo_titulo.nombre, _tipo_dart(campo_titulo.tipo_java))
    else:
        titulo_expr = "'ID: ${item.id}'"

    lineas_detalle = _lineas_detalle_item(entidad, entidades_por_nombre, campo_titulo)
    if not lineas_detalle:
        lineas_detalle = ["                      Text('id: ${item.id}'),"]
    detalle_str = "\n".join(lineas_detalle)

    imports_voz = ""
    campos_voz = ""
    campo_items_actuales = ""
    guardar_items_actuales = ""
    metodo_escuchar = ""
    boton_voz = ""
    if es_entidad_voz:
        imports_voz = (
            f"import 'package:speech_to_text/speech_to_text.dart';\n"
            f"import '../local/{archivo_modelo}_comando_voz.dart';\n"
        )
        campo_items_actuales = f"  List<{clase}> _itemsActuales = [];\n"
        guardar_items_actuales = "      _itemsActuales = datos;\n"
        campos_voz = "  final SpeechToText _speech = SpeechToText();\n"
        metodo_escuchar = f"""
  Future<void> _escucharComando() async {{
    final disponible = await _speech.initialize();
    if (!disponible) {{
      if (mounted) {{
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No se pudo iniciar el reconocimiento de voz.')),
        );
      }}
      return;
    }}
    _speech.listen(onResult: (resultado) async {{
      if (resultado.finalResult) {{
        final comando = interpretarComando{clase}(resultado.recognizedWords);
        await ejecutarComando{clase}(context, comando, _itemsActuales, _cargar);
      }}
    }});
  }}
"""
        boton_voz = f"""      floatingActionButton: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          FloatingActionButton(
            heroTag: '{archivo_modelo}_mic',
            onPressed: _escucharComando,
            tooltip: 'Comando de voz',
            child: const Icon(Icons.mic),
          ),
          const SizedBox(height: 12),
          FloatingActionButton(
            heroTag: '{archivo_modelo}_add',
            onPressed: () async {{
              await Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const {clase}FormScreen()),
              );
              _cargar();
            }},
            child: const Icon(Icons.add),
          ),
        ],
      ),"""
    else:
        boton_voz = f"""      floatingActionButton: FloatingActionButton(
        onPressed: () async {{
          await Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const {clase}FormScreen()),
          );
          _cargar();
        }},
        child: const Icon(Icons.add),
      ),"""

    return f"""import 'package:flutter/material.dart';
import '../models/{archivo_modelo}.dart';
import '../services/{archivo_modelo}_service.dart';
import '../local/local_db.dart';
import '../local/sync_service.dart';
import '../local/connectivity_banner.dart';
import '../local/conflict_dialog.dart';
{imports_voz}import '{archivo_modelo}_form_screen.dart';

class {clase}ListScreen extends StatefulWidget {{
  const {clase}ListScreen({{super.key}});

  @override
  State<{clase}ListScreen> createState() => _{clase}ListScreenState();
}}

class _{clase}ListScreenState extends State<{clase}ListScreen> {{
  final _service = {clase}Service();
  late Future<List<{clase}>> _futuro;
{campo_items_actuales}{campos_voz}
  @override
  void initState() {{
    super.initState();
    _cargar();
  }}

  void _cargar() {{
    setState(() {{
      _futuro = _cargarConFallback();
    }});
    WidgetsBinding.instance.addPostFrameCallback((_) {{
      if (mounted) mostrarConflictosPendientes(context, '{clase}', _cargar);
    }});
  }}

  Future<List<{clase}>> _cargarConFallback() async {{
    try {{
      final datos = await _service.listar();
      for (final item in datos) {{
        if (item.id != null) {{
          await LocalDb.instancia.guardarCache('{clase}', item.id!, item.toJson());
        }}
      }}
{guardar_items_actuales}      return datos;
    }} catch (_) {{
      final cache = await LocalDb.instancia.listarCache('{clase}');
      final datos = cache.map((json) => {clase}.fromJson(json)).toList();
{guardar_items_actuales}      return datos;
    }}
  }}
{metodo_escuchar}
  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      appBar: AppBar(title: const Text('{entidad.nombre_original}')),
      body: Column(
        children: [
          ConnectivityBanner(entidad: '{clase}'),
          Expanded(
            child: FutureBuilder<List<{clase}>>(
              future: _futuro,
              builder: (context, snapshot) {{
                if (snapshot.connectionState == ConnectionState.waiting) {{
                  return const Center(child: CircularProgressIndicator());
                }}
                if (snapshot.hasError) {{
                  return Center(child: Text('Error: ${{snapshot.error}}'));
                }}
                final items = snapshot.data ?? [];
                if (items.isEmpty) {{
                  return const Center(child: Text('No hay registros todavía.'));
                }}
                return ListView.builder(
                  itemCount: items.length,
                  itemBuilder: (context, index) {{
                    final item = items[index];
                    return Card(
                      clipBehavior: Clip.antiAlias,
                      child: InkWell(
                        onTap: () async {{
                          await Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => {clase}FormScreen(entidad: item)),
                          );
                          _cargar();
                        }},
                        child: ListTile(
                          title: Text({titulo_expr}),
                          subtitle: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
{detalle_str}
                            ],
                          ),
                          trailing: IconButton(
                            icon: const Icon(Icons.delete),
                            onPressed: () async {{
                              await SyncService.instancia.eliminar('{clase}', item.id!);
                              _cargar();
                            }},
                          ),
                        ),
                      ),
                    );
                  }},
                );
              }},
            ),
          ),
        ],
      ),
{boton_voz}
    );
  }}
}}
"""


def _renderizar_form_screen(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> str:
    archivo_modelo = _snake(entidad.nombre_java)
    clase = entidad.nombre_java
    campos = _campos_dart(entidad, entidades_por_nombre)
    relaciones_incluidas = [c for c in campos if c.es_relacion]

    declaraciones = []
    inicializaciones = []
    widgets = []
    constructor_args = []

    if relaciones_incluidas:
        declaraciones.append("  bool _cargandoOpciones = true;")

    for c in campos:
        if c.es_relacion:
            base = c.nombre[:-2]  # quita el "Id" agregado en _campos_dart
            rel_clase = c.entidad_relacionada
            campo_texto = _campo_texto(entidades_por_nombre[rel_clase], entidades_por_nombre)
            texto_opcion = (
                f"opcion.{campo_texto.nombre} ?? '{rel_clase} #${{opcion.id}}'"
                if campo_texto is not None
                else f"'{rel_clase} #${{opcion.id}}'"
            )
            declaraciones.append(f"  int? {c.nombre};")
            declaraciones.append(f"  List<{rel_clase}> _{base}Opciones = [];")
            inicializaciones.append(f"    {c.nombre} = widget.entidad?.{c.nombre};")
            widgets.append(
                f"              DropdownButtonFormField<int>(\n"
                f"                value: (_cargandoOpciones || !_{base}Opciones.any((o) => o.id == {c.nombre}))"
                f" ? null : {c.nombre},\n"
                f"                decoration: InputDecoration(\n"
                f"                  labelText: '{rel_clase}',\n"
                f"                  hintText: _cargandoOpciones\n"
                f"                      ? 'Cargando...'\n"
                f"                      : (_{base}Opciones.isEmpty ? 'No hay {rel_clase} registrados todavía' : null),\n"
                f"                ),\n"
                f"                items: _cargandoOpciones\n"
                f"                    ? const []\n"
                f"                    : _{base}Opciones\n"
                f"                        .map((opcion) => DropdownMenuItem<int>(\n"
                f"                              value: opcion.id,\n"
                f"                              child: Text({texto_opcion}),\n"
                f"                            ))\n"
                f"                        .toList(),\n"
                f"                onChanged: (_cargandoOpciones || _{base}Opciones.isEmpty)\n"
                f"                    ? null\n"
                f"                    : (valor) => setState(() => {c.nombre} = valor),\n"
                f"              ),\n"
                f"              const SizedBox(height: 12),"
            )
            constructor_args.append(f"      {c.nombre}: {c.nombre},")
            continue

        etiqueta = c.nombre
        if c.tipo_dart == "bool":
            declaraciones.append(f"  bool {c.nombre} = false;")
            inicializaciones.append(f"    {c.nombre} = widget.entidad?.{c.nombre} ?? false;")
            widgets.append(
                f"              CheckboxListTile(\n"
                f"                title: const Text('{etiqueta}'),\n"
                f"                value: {c.nombre},\n"
                f"                onChanged: (valor) => setState(() => {c.nombre} = valor ?? false),\n"
                f"              ),"
            )
            constructor_args.append(f"      {c.nombre}: {c.nombre},")
        else:
            declaraciones.append(f"  late TextEditingController _{c.nombre}Controller;")
            if c.tipo_dart == "List<String>":
                inicializaciones.append(
                    f"    _{c.nombre}Controller = TextEditingController(text: widget.entidad?.{c.nombre}?.join(', '));"
                )
            elif c.tipo_dart == "DateTime":
                inicializaciones.append(
                    f"    _{c.nombre}Controller = TextEditingController("
                    f"text: widget.entidad?.{c.nombre} != null ? widget.entidad!.{c.nombre}!.toIso8601String().split('T').first : null);"
                )
            else:
                inicializaciones.append(
                    f"    _{c.nombre}Controller = TextEditingController(text: widget.entidad?.{c.nombre}?.toString());"
                )
            teclado = ", keyboardType: TextInputType.number" if c.tipo_dart in ("int", "double") else ""
            widgets.append(
                f"              TextFormField(\n"
                f"                controller: _{c.nombre}Controller,\n"
                f"                decoration: const InputDecoration(labelText: '{etiqueta}'){teclado},\n"
                f"              ),\n"
                f"              const SizedBox(height: 12),"
            )
            if c.tipo_dart == "int":
                constructor_args.append(f"      {c.nombre}: int.tryParse(_{c.nombre}Controller.text),")
            elif c.tipo_dart == "double":
                constructor_args.append(f"      {c.nombre}: double.tryParse(_{c.nombre}Controller.text),")
            elif c.tipo_dart == "DateTime":
                constructor_args.append(f"      {c.nombre}: DateTime.tryParse(_{c.nombre}Controller.text),")
            elif c.tipo_dart == "List<String>":
                constructor_args.append(
                    f"      {c.nombre}: _{c.nombre}Controller.text.trim().isEmpty"
                    f" ? [] : _{c.nombre}Controller.text.split(',').map((s) => s.trim()).toList(),"
                )
            else:
                constructor_args.append(f"      {c.nombre}: _{c.nombre}Controller.text,")

    imports_relaciones: list[str] = []
    vistas: set[str] = set()
    for c in relaciones_incluidas:
        if c.entidad_relacionada in vistas:
            continue
        vistas.add(c.entidad_relacionada)
        archivo_rel = _snake(c.entidad_relacionada)
        if c.entidad_relacionada != entidad.nombre_java:
            imports_relaciones.append(f"import '../models/{archivo_rel}.dart';")
        imports_relaciones.append(f"import '../services/{archivo_rel}_service.dart';")
    imports_relaciones_str = ("\n".join(imports_relaciones) + "\n") if imports_relaciones else ""

    metodo_cargar_opciones = ""
    llamada_cargar_opciones = ""
    if relaciones_incluidas:
        llamada_cargar_opciones = "    _cargarOpciones();\n"
        awaits = "\n".join(
            f"      final {c.nombre[:-2]}Opciones = await {c.entidad_relacionada}Service().listar();"
            for c in relaciones_incluidas
        )
        asignaciones = "\n".join(
            f"        _{c.nombre[:-2]}Opciones = {c.nombre[:-2]}Opciones;" for c in relaciones_incluidas
        )
        metodo_cargar_opciones = f"""
  Future<void> _cargarOpciones() async {{
    try {{
{awaits}
      if (!mounted) return;
      setState(() {{
{asignaciones}
        _cargandoOpciones = false;
      }});
    }} catch (_) {{
      if (mounted) setState(() => _cargandoOpciones = false);
    }}
  }}
"""

    return f"""import 'package:flutter/material.dart';
import '../models/{archivo_modelo}.dart';
{imports_relaciones_str}import '../local/sync_service.dart';

class {clase}FormScreen extends StatefulWidget {{
  final {clase}? entidad;
  const {clase}FormScreen({{super.key, this.entidad}});

  @override
  State<{clase}FormScreen> createState() => _{clase}FormScreenState();
}}

class _{clase}FormScreenState extends State<{clase}FormScreen> {{
  final _formKey = GlobalKey<FormState>();

{chr(10).join(declaraciones)}

  @override
  void initState() {{
    super.initState();
{chr(10).join(inicializaciones)}
{llamada_cargar_opciones}  }}
{metodo_cargar_opciones}
  Future<void> _guardar() async {{
    if (!_formKey.currentState!.validate()) return;
    final entidad = {clase}(
      id: widget.entidad?.id,
{chr(10).join(constructor_args)}
    );
    // Guarda localmente y encola la sincronización primero (modo offline);
    // si hay conexión, SyncService intenta sincronizar de inmediato.
    if (widget.entidad == null) {{
      await SyncService.instancia.crear('{clase}', entidad.toJson());
    }} else {{
      await SyncService.instancia.actualizar(
        '{clase}', entidad.id!, entidad.toJson(), widget.entidad!.toJson(),
      );
    }}
    if (mounted) Navigator.pop(context);
  }}

  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      appBar: AppBar(title: Text(widget.entidad == null ? 'Nueva {entidad.nombre_original}' : 'Editar {entidad.nombre_original}')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: ListView(
            children: [
{chr(10).join(widgets)}
              const SizedBox(height: 24),
              ElevatedButton(onPressed: _guardar, child: const Text('Guardar')),
            ],
          ),
        ),
      ),
    );
  }}
}}
"""


def _renderizar_main(nombre_app: str) -> str:
    return f"""import 'package:flutter/material.dart';
import 'screens/home_screen.dart';
import 'local/registro_sync.dart';

void main() {{
  registrarHandlersSync();
  runApp(const MiApp());
}}

class MiApp extends StatelessWidget {{
  const MiApp({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return MaterialApp(
      title: '{nombre_app}',
      theme: ThemeData(colorSchemeSeed: Colors.blue, useMaterial3: true),
      home: const HomeScreen(),
    );
  }}
}}
"""


def _renderizar_home_screen(entidades: list[EntidadModelo], nombre_app: str) -> str:
    # HomeScreen es un widget aparte (no el contenido inline de MiApp.build):
    # así el `context` que usa Navigator.push ya está por debajo del
    # Navigator que crea MaterialApp, y no tira
    # "Navigator operation requested with a context that does not include a Navigator".
    imports = "\n".join(f"import '{_snake(e.nombre_java)}_list_screen.dart';" for e in entidades)

    tarjetas = []
    for i, e in enumerate(entidades):
        color, icono = _PALETA_TARJETAS[i % len(_PALETA_TARJETAS)]
        tarjetas.append(
            f"""      _TarjetaEntidad(
        nombre: '{e.nombre_original}',
        icono: {icono},
        color: {color},
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const {e.nombre_java}ListScreen()),
        ),
      ),"""
        )
    tarjetas_str = "\n".join(tarjetas)

    return f"""import 'package:flutter/material.dart';
{imports}

class HomeScreen extends StatelessWidget {{
  const HomeScreen({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      appBar: AppBar(title: const Text('{nombre_app}')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: GridView.count(
          crossAxisCount: 2,
          mainAxisSpacing: 16,
          crossAxisSpacing: 16,
          children: [
{tarjetas_str}
          ],
        ),
      ),
    );
  }}
}}

class _TarjetaEntidad extends StatelessWidget {{
  final String nombre;
  final IconData icono;
  final MaterialColor color;
  final VoidCallback onTap;

  const _TarjetaEntidad({{
    required this.nombre,
    required this.icono,
    required this.color,
    required this.onTap,
  }});

  @override
  Widget build(BuildContext context) {{
    return Card(
      color: color.shade50,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icono, size: 40, color: color.shade700),
              const SizedBox(height: 12),
              Text(
                nombre,
                textAlign: TextAlign.center,
                style: TextStyle(fontWeight: FontWeight.bold, color: color.shade900),
              ),
            ],
          ),
        ),
      ),
    );
  }}
}}
"""


def _fusionar_pubspec(pubspec_plantilla: str, nombre_paquete: str, *, con_voz: bool) -> str:
    """Parte del pubspec.yaml tal cual lo generó `flutter create` en la
    plantilla base y sólo le cambia el nombre/descripción del proyecto y le
    asegura las dependencias que necesita el código generado — todo lo demás
    (versión de SDK, lints, cupertino_icons, etc.) queda como lo trae Flutter.

    `sqflite`/`path`/`connectivity_plus` (modo offline, CU14) se agregan
    siempre; `speech_to_text` solo si el diagrama tiene una entidad candidata
    a comando de voz (ver `_entidad_candidata_voz`)."""
    descripcion = "Frontend generado automáticamente a partir de un diagrama de clases UML."
    resultado = re.sub(r"(?m)^name:.*$", f"name: {nombre_paquete}", pubspec_plantilla, count=1)
    resultado = re.sub(r"(?m)^description:.*$", f"description: {descripcion}", resultado, count=1)

    dependencias_nuevas = ["http: ^1.2.0", "sqflite: ^2.4.1", "path: ^1.9.0", "connectivity_plus: ^6.1.3"]
    if con_voz:
        dependencias_nuevas.append("speech_to_text: ^7.0.0")

    lineas_a_agregar = [
        f"  {dep}"
        for dep in dependencias_nuevas
        if not re.search(rf"(?m)^\s*{re.escape(dep.split(':')[0])}:\s*", resultado)
    ]
    if lineas_a_agregar:
        resultado = re.sub(
            r"(?m)^(\s*flutter:\n\s*sdk: flutter\n)",
            r"\1" + "\n".join(lineas_a_agregar) + "\n",
            resultado,
            count=1,
        )
    return resultado


_ARCHIVOS_IGNORADOS_PLANTILLA = (".git", ".dart_tool", ".idea", "build")

_RUTA_ANDROID_MANIFEST = "android/app/src/main/AndroidManifest.xml"


def _copiar_plantilla_al_zip(zip_file: zipfile.ZipFile) -> None:
    """Copia toda la plantilla Flutter base al zip, salvo pubspec.yaml (se
    escribe aparte, fusionado), AndroidManifest.xml (se escribe aparte,
    posiblemente con el permiso de micrófono de CU14) y lib/ (se reemplaza
    por completo con el código generado del diagrama)."""
    for path in sorted(_PLANTILLA_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(_PLANTILLA_DIR)
        rel_str = str(rel).replace("\\", "/")
        if rel_str in ("pubspec.yaml", "pubspec.lock", "README.md", _RUTA_ANDROID_MANIFEST) or rel_str.startswith(
            ("lib/", "test/")
        ):
            # test/widget_test.dart es el smoke test por defecto de `flutter
            # create`: referencia el nombre de paquete y el widget (MyApp) de
            # la plantilla, no del proyecto generado — no aplica acá.
            continue
        if any(parte in _ARCHIVOS_IGNORADOS_PLANTILLA or parte.endswith(".iml") for parte in rel.parts):
            continue
        zip_file.write(path, arcname=rel_str)


def _android_manifest(contenido_original: str, con_microfono: bool) -> str:
    """CU14 (B.3): agrega el permiso de grabar audio solo si hay una entidad
    candidata a comando de voz — si no, el manifest queda tal cual lo trae la
    plantilla, sin pedir un permiso que la app generada no va a usar."""
    if not con_microfono or "android.permission.RECORD_AUDIO" in contenido_original:
        return contenido_original
    permiso = '    <uses-permission android:name="android.permission.RECORD_AUDIO" />\n'
    return re.sub(r"(?m)^(<manifest[^>]*>\n)", r"\1" + permiso, contenido_original, count=1)


def _api_config(host: str) -> str:
    return f"""// Backend generado por CU11, corriendo por defecto en {host}.
// Si corrés el backend en otra dirección (ej. un emulador Android, que ve
// "localhost" de la máquina host como 10.0.2.2), cambiá este valor.
const String baseUrl = '{host}/api';
"""


def _readme(nombre_app: str, entidades: list[EntidadModelo], entidad_voz: EntidadModelo | None) -> str:
    pantallas = "\n".join(f"- `{e.nombre_original}`: listado + alta/edición/baja" for e in entidades)
    if entidad_voz is not None:
        seccion_voz = (
            f"Se detectó a `{entidad_voz.nombre_original}` como entidad candidata para comando de voz "
            "(tiene fecha, 2+ relaciones y no es superclase de herencia) — su pantalla de listado tiene "
            "un botón de micrófono adicional. El parser de voz es un conjunto de reglas Dart generado a "
            "medida para sus atributos (nada de IA externa); reconoce \"crear\", \"editar ... de ... a ...\" "
            "y \"eliminar ...\"."
        )
    else:
        seccion_voz = (
            "Ninguna entidad del diagrama cumplió los criterios para comando de voz (atributo de fecha, "
            "2 o más relaciones hacia otras entidades, y no ser superclase de herencia) — no se generó "
            "ningún botón de micrófono ni parser de voz para este proyecto."
        )
    return f"""# {nombre_app}

Frontend generado automáticamente a partir de un diagrama de clases UML, para
consumir el backend generado por el mismo sistema (Spring Boot).

## Cómo correrlo

```
flutter pub get
flutter run
```

Por defecto apunta a `http://localhost:8080/api` (`lib/services/api_config.dart`) —
ahí tiene que estar corriendo el backend generado (`mvn spring-boot:run`).

## Pantallas generadas

{pantallas}

## Modo offline (CU14)

Todas las pantallas guardan localmente (SQLite, vía `sqflite`) cada
creación/edición/eliminación y la encolan para sincronizar contra el backend;
si hay conexión, se sincroniza al toque, si no, queda pendiente y se
reintenta solo al reconectar o al volver a abrir la lista. Las pantallas de
lista muestran un banner ("Sin conexión..." / "N cambios pendientes...")
cuando corresponde. Si el servidor devuelve un registro distinto al que
había cuando se editó offline, se guarda como conflicto y se le pregunta al
usuario cuál versión conservar la próxima vez que abre esa lista.

**Esto solo funciona en Android** (`sqflite` no corre en Flutter Web sin
paquetes adicionales) — en Web las pantallas siguen andando online, sin
persistencia local ni cola de sincronización.

{seccion_voz}

Limitaciones conocidas (aceptables para este alcance, no bugs a resolver):
la cola de sincronización no tiene reintentos con backoff ni maneja
dependencias entre operaciones encadenadas, y los registros creados sin
conexión no reconcilian referencias entre sí si se relacionan entre ellos
antes de sincronizar.

## Simplificaciones a tener en cuenta

- Los campos que son relaciones con otra clase se muestran como un ID numérico
  simple, no como un selector que busca la entidad relacionada (tampoco se
  muestran en el detalle de la lista, solo los atributos propios y heredados).
- Las relaciones de tipo lista (uno a muchos, muchos a muchos) no se muestran
  en las pantallas generadas.
"""


def generar_zip_frontend(contenido: dict, nombre_proyecto: str) -> bytes:
    modelo: ModeloBackend = construir_modelo_backend(contenido, nombre_proyecto)
    nombre_paquete = modelo.paquete.rsplit(".", 1)[-1]
    entidades_por_nombre = {e.nombre_java: e for e in modelo.entidades}
    entidad_voz = _entidad_candidata_voz(modelo, entidades_por_nombre)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        _copiar_plantilla_al_zip(zip_file)

        pubspec_plantilla = (_PLANTILLA_DIR / "pubspec.yaml").read_text(encoding="utf-8")
        zip_file.writestr(
            "pubspec.yaml", _fusionar_pubspec(pubspec_plantilla, nombre_paquete, con_voz=entidad_voz is not None)
        )
        zip_file.writestr("README.md", _readme(nombre_proyecto, modelo.entidades, entidad_voz))
        zip_file.writestr("lib/main.dart", _renderizar_main(nombre_proyecto))
        zip_file.writestr("lib/screens/home_screen.dart", _renderizar_home_screen(modelo.entidades, nombre_proyecto))
        zip_file.writestr("lib/services/api_config.dart", _api_config("http://localhost:8080"))

        manifest_original = (_PLANTILLA_DIR / _RUTA_ANDROID_MANIFEST).read_text(encoding="utf-8")
        zip_file.writestr(_RUTA_ANDROID_MANIFEST, _android_manifest(manifest_original, entidad_voz is not None))

        zip_file.writestr("lib/local/local_db.dart", _LOCAL_DB_DART)
        zip_file.writestr("lib/local/sync_service.dart", _SYNC_SERVICE_DART)
        zip_file.writestr("lib/local/connectivity_banner.dart", _CONNECTIVITY_BANNER_DART)
        zip_file.writestr("lib/local/conflict_dialog.dart", _CONFLICT_DIALOG_DART)
        zip_file.writestr("lib/local/registro_sync.dart", _renderizar_registro_sync(modelo))

        for entidad in modelo.entidades:
            archivo = _snake(entidad.nombre_java)
            es_voz = entidad_voz is not None and entidad.nombre_java == entidad_voz.nombre_java
            zip_file.writestr(f"lib/models/{archivo}.dart", _renderizar_modelo(entidad, entidades_por_nombre))
            zip_file.writestr(f"lib/services/{archivo}_service.dart", _renderizar_service(entidad))
            zip_file.writestr(
                f"lib/screens/{archivo}_list_screen.dart",
                _renderizar_list_screen(entidad, entidades_por_nombre, es_entidad_voz=es_voz),
            )
            zip_file.writestr(
                f"lib/screens/{archivo}_form_screen.dart", _renderizar_form_screen(entidad, entidades_por_nombre)
            )
            if es_voz:
                zip_file.writestr(
                    f"lib/local/{archivo}_comando_voz.dart", _renderizar_parser_voz(entidad, entidades_por_nombre)
                )

    return buffer.getvalue()
