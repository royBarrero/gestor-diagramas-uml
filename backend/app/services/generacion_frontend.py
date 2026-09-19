"""CU12: genera una app Flutter (Dart, `package:http`, sin manejo de estado
externo) a partir del mismo modelo estructural que ya usa `generacion_backend.py`
(`modelo_backend.construir_modelo_backend`) — listados y formularios CRUD por
entidad, apuntando a los endpoints `/api/...` que genera CU11.

Simplificaciones documentadas (acordadas con el usuario):
- Los campos de relación (`@ManyToOne`/`@OneToOne` dueño) se muestran como un
  input numérico simple ("ID de {Entidad}"), no como un selector que busca la
  entidad relacionada. En el JSON que devuelve el backend generado viajan como
  un objeto anidado (`{"persona": {"id": 3}}`, no `{"personaId": 3}`) porque
  así es como Jackson serializa una relación JPA — el modelo Dart lee/escribe
  ese anidado y lo expone como un `int?` plano.
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

    def __init__(self, nombre: str, tipo_dart: str, es_relacion: bool = False):
        self.nombre = nombre
        self.tipo_dart = tipo_dart
        self.es_relacion = es_relacion


def _campos_dart(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> list[_Campo]:
    campos = [_Campo(c.nombre, _tipo_dart(c.tipo_java)) for c in todos_los_campos(entidad, entidades_por_nombre)]
    campos += [_Campo(f"{r.nombre}Id", "int", es_relacion=True) for r in _relaciones_incluidas(entidad)]
    return campos


def _renderizar_modelo(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> str:
    tipo_id_dart = _tipo_dart(entidad.campo_id_tipo)
    campos = _campos_dart(entidad, entidades_por_nombre)

    props = [f"  {c.tipo_dart}? {c.nombre};" for c in campos]

    lineas_from_json = []
    for c in campos:
        if c.es_relacion:
            nombre_relacion = c.nombre[:-2]  # quita el "Id" agregado en _campos_dart
            lineas_from_json.append(
                f"      {c.nombre}: json['{nombre_relacion}'] != null ? json['{nombre_relacion}']['id'] : null,"
            )
        elif c.tipo_dart == "DateTime":
            lineas_from_json.append(f"      {c.nombre}: json['{c.nombre}'] != null ? DateTime.tryParse(json['{c.nombre}']) : null,")
        elif c.tipo_dart == "List<String>":
            lineas_from_json.append(f"      {c.nombre}: json['{c.nombre}'] != null ? List<String>.from(json['{c.nombre}']) : null,")
        else:
            lineas_from_json.append(f"      {c.nombre}: json['{c.nombre}'],")

    lineas_to_json = []
    for c in campos:
        if c.es_relacion:
            nombre_relacion = c.nombre[:-2]
            lineas_to_json.append(f"      '{nombre_relacion}': {c.nombre} != null ? {{'id': {c.nombre}}} : null,")
        elif c.tipo_dart == "DateTime":
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


def _titulo_item(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> str:
    campos = todos_los_campos(entidad, entidades_por_nombre)
    campos_texto = [c for c in campos if c.tipo_java in ("String", "char")]
    if campos_texto:
        return "item." + campos_texto[0].nombre
    if campos:
        return "item." + campos[0].nombre + ".toString()"
    return "'ID: ${item.id}'"


def _renderizar_list_screen(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> str:
    archivo_modelo = _snake(entidad.nombre_java)
    clase = entidad.nombre_java
    titulo = _titulo_item(entidad, entidades_por_nombre)
    titulo_expr = titulo if titulo.startswith("'") else f"'${{{titulo}}}'"
    return f"""import 'package:flutter/material.dart';
import '../models/{archivo_modelo}.dart';
import '../services/{archivo_modelo}_service.dart';
import '{archivo_modelo}_form_screen.dart';

class {clase}ListScreen extends StatefulWidget {{
  const {clase}ListScreen({{super.key}});

  @override
  State<{clase}ListScreen> createState() => _{clase}ListScreenState();
}}

class _{clase}ListScreenState extends State<{clase}ListScreen> {{
  final _service = {clase}Service();
  late Future<List<{clase}>> _futuro;

  @override
  void initState() {{
    super.initState();
    _cargar();
  }}

  void _cargar() {{
    setState(() {{
      _futuro = _service.listar();
    }});
  }}

  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      appBar: AppBar(title: const Text('{entidad.nombre_original}')),
      body: FutureBuilder<List<{clase}>>(
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
              return ListTile(
                title: Text({titulo_expr}),
                subtitle: Text('id: ${{item.id}}'),
                onTap: () async {{
                  await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => {clase}FormScreen(entidad: item)),
                  );
                  _cargar();
                }},
                trailing: IconButton(
                  icon: const Icon(Icons.delete),
                  onPressed: () async {{
                    await _service.eliminar(item.id!);
                    _cargar();
                  }},
                ),
              );
            }},
          );
        }},
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {{
          await Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const {clase}FormScreen()),
          );
          _cargar();
        }},
        child: const Icon(Icons.add),
      ),
    );
  }}
}}
"""


def _renderizar_form_screen(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> str:
    archivo_modelo = _snake(entidad.nombre_java)
    clase = entidad.nombre_java
    campos = _campos_dart(entidad, entidades_por_nombre)

    declaraciones = []
    inicializaciones = []
    widgets = []
    constructor_args = []

    for c in campos:
        etiqueta = f"ID de {c.nombre[:-2]}" if c.es_relacion else c.nombre
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

    return f"""import 'package:flutter/material.dart';
import '../models/{archivo_modelo}.dart';
import '../services/{archivo_modelo}_service.dart';

class {clase}FormScreen extends StatefulWidget {{
  final {clase}? entidad;
  const {clase}FormScreen({{super.key, this.entidad}});

  @override
  State<{clase}FormScreen> createState() => _{clase}FormScreenState();
}}

class _{clase}FormScreenState extends State<{clase}FormScreen> {{
  final _formKey = GlobalKey<FormState>();
  final _service = {clase}Service();

{chr(10).join(declaraciones)}

  @override
  void initState() {{
    super.initState();
{chr(10).join(inicializaciones)}
  }}

  Future<void> _guardar() async {{
    if (!_formKey.currentState!.validate()) return;
    final entidad = {clase}(
      id: widget.entidad?.id,
{chr(10).join(constructor_args)}
    );
    if (widget.entidad == null) {{
      await _service.crear(entidad);
    }} else {{
      await _service.actualizar(entidad.id!, entidad);
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

void main() {{
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


def _fusionar_pubspec(pubspec_plantilla: str, nombre_paquete: str) -> str:
    """Parte del pubspec.yaml tal cual lo generó `flutter create` en la
    plantilla base y sólo le cambia el nombre/descripción del proyecto y le
    asegura la dependencia `http` — todo lo demás (versión de SDK, lints,
    cupertino_icons, etc.) queda como lo trae Flutter."""
    descripcion = "Frontend generado automáticamente a partir de un diagrama de clases UML."
    resultado = re.sub(r"(?m)^name:.*$", f"name: {nombre_paquete}", pubspec_plantilla, count=1)
    resultado = re.sub(r"(?m)^description:.*$", f"description: {descripcion}", resultado, count=1)
    if not re.search(r"(?m)^\s*http:\s*\^", resultado):
        resultado = re.sub(
            r"(?m)^(\s*flutter:\n\s*sdk: flutter\n)",
            r"\1  http: ^1.2.0\n",
            resultado,
            count=1,
        )
    return resultado


_ARCHIVOS_IGNORADOS_PLANTILLA = (".git", ".dart_tool", ".idea", "build")


def _copiar_plantilla_al_zip(zip_file: zipfile.ZipFile) -> None:
    """Copia toda la plantilla Flutter base al zip, salvo pubspec.yaml (se
    escribe aparte, fusionado) y lib/ (se reemplaza por completo con el
    código generado del diagrama)."""
    for path in sorted(_PLANTILLA_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(_PLANTILLA_DIR)
        rel_str = str(rel).replace("\\", "/")
        if rel_str in ("pubspec.yaml", "pubspec.lock", "README.md") or rel_str.startswith(("lib/", "test/")):
            # test/widget_test.dart es el smoke test por defecto de `flutter
            # create`: referencia el nombre de paquete y el widget (MyApp) de
            # la plantilla, no del proyecto generado — no aplica acá.
            continue
        if any(parte in _ARCHIVOS_IGNORADOS_PLANTILLA or parte.endswith(".iml") for parte in rel.parts):
            continue
        zip_file.write(path, arcname=rel_str)


def _api_config(host: str) -> str:
    return f"""// Backend generado por CU11, corriendo por defecto en {host}.
// Si corrés el backend en otra dirección (ej. un emulador Android, que ve
// "localhost" de la máquina host como 10.0.2.2), cambiá este valor.
const String baseUrl = '{host}/api';
"""


def _readme(nombre_app: str, entidades: list[EntidadModelo]) -> str:
    pantallas = "\n".join(f"- `{e.nombre_original}`: listado + alta/edición/baja" for e in entidades)
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

## Simplificaciones a tener en cuenta

- Los campos que son relaciones con otra clase se muestran como un ID numérico
  simple, no como un selector que busca la entidad relacionada.
- Las relaciones de tipo lista (uno a muchos, muchos a muchos) no se muestran
  en las pantallas generadas.
"""


def generar_zip_frontend(contenido: dict, nombre_proyecto: str) -> bytes:
    modelo: ModeloBackend = construir_modelo_backend(contenido, nombre_proyecto)
    nombre_paquete = modelo.paquete.rsplit(".", 1)[-1]
    entidades_por_nombre = {e.nombre_java: e for e in modelo.entidades}

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        _copiar_plantilla_al_zip(zip_file)

        pubspec_plantilla = (_PLANTILLA_DIR / "pubspec.yaml").read_text(encoding="utf-8")
        zip_file.writestr("pubspec.yaml", _fusionar_pubspec(pubspec_plantilla, nombre_paquete))
        zip_file.writestr("README.md", _readme(nombre_proyecto, modelo.entidades))
        zip_file.writestr("lib/main.dart", _renderizar_main(nombre_proyecto))
        zip_file.writestr("lib/screens/home_screen.dart", _renderizar_home_screen(modelo.entidades, nombre_proyecto))
        zip_file.writestr("lib/services/api_config.dart", _api_config("http://localhost:8080"))

        for entidad in modelo.entidades:
            archivo = _snake(entidad.nombre_java)
            zip_file.writestr(f"lib/models/{archivo}.dart", _renderizar_modelo(entidad, entidades_por_nombre))
            zip_file.writestr(f"lib/services/{archivo}_service.dart", _renderizar_service(entidad))
            zip_file.writestr(
                f"lib/screens/{archivo}_list_screen.dart", _renderizar_list_screen(entidad, entidades_por_nombre)
            )
            zip_file.writestr(
                f"lib/screens/{archivo}_form_screen.dart", _renderizar_form_screen(entidad, entidades_por_nombre)
            )

    return buffer.getvalue()
