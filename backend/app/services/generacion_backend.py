"""CU11: genera un proyecto Spring Boot (Maven, Java 17, JPA + H2) a partir
del modelo estructural de `modelo_backend.py`, empaquetado en memoria como
.zip (sin escribir a disco, mismo criterio in-memory que ya usan los
exports de JSON/XMI en `exportacion_diagrama.py` / `xmi_diagrama.py`).

Cada entidad genera 5 archivos Java: modelo JPA (`model/`), DTO (`dto/`),
repository, service y controller. Los Controllers sólo hablan en DTOs (nunca
exponen las entidades JPA directamente) para evitar loops de serialización
en relaciones bidireccionales; el Service es quien resuelve los ids de
relación contra los repositories correspondientes. El proyecto generado
también incluye CORS habilitado por defecto (`config/CorsConfig.java`) y
manejo global de errores (`exception/`), generados una única vez.
"""

import io
import zipfile

from app.services.exportacion_diagrama import nombre_archivo_descarga
from app.services.modelo_backend import (
    CampoModelo,
    EntidadModelo,
    ModeloBackend,
    campos_heredados,
    construir_modelo_backend,
)

__all__ = ["generar_zip_backend", "nombre_zip_backend"]


def nombre_zip_backend(nombre_proyecto: str) -> str:
    return nombre_archivo_descarga(f"{nombre_proyecto} backend", "zip")


def _getter(campo_nombre: str, tipo_java: str) -> str:
    prefijo = "is" if tipo_java == "boolean" else "get"
    return f"{prefijo}{campo_nombre[:1].upper()}{campo_nombre[1:]}"


def _setter(campo_nombre: str) -> str:
    return f"set{campo_nombre[:1].upper()}{campo_nombre[1:]}"


def _bloque_getter_setter(nombre: str, tipo: str) -> str:
    getter, setter = _getter(nombre, tipo), _setter(nombre)
    return (
        f"    public {tipo} {getter}() {{\n"
        f"        return {nombre};\n"
        f"    }}\n\n"
        f"    public void {setter}({tipo} {nombre}) {{\n"
        f"        this.{nombre} = {nombre};\n"
        f"    }}\n"
    )


def _relaciones_propietarias(entidad: EntidadModelo) -> list:
    return [r for r in entidad.relaciones if r.propietaria]


# --------------------------------------------------------------------------
# model/{Entidad}.java
# --------------------------------------------------------------------------


def _imports_entidad(entidad: EntidadModelo) -> list[str]:
    imports = {"jakarta.persistence.*"}
    if any(c.es_lista for c in entidad.campos) or any(r.es_coleccion for r in entidad.relaciones):
        imports.add("java.util.List")
        imports.add("java.util.ArrayList")
    if any(c.tipo_java == "LocalDate" for c in entidad.campos):
        imports.add("java.time.LocalDate")
    if any(not r.propietaria for r in entidad.relaciones):
        imports.add("com.fasterxml.jackson.annotation.JsonIgnore")
    return sorted(imports)


def _campo_relacion_anotacion(rel) -> str:
    anotacion = {
        "oneToOne": "OneToOne",
        "manyToOne": "ManyToOne",
        "oneToMany": "OneToMany",
        "manyToMany": "ManyToMany",
    }[rel.tipo]

    atributos = []
    if rel.mapped_by:
        atributos.append(f'mappedBy = "{rel.mapped_by}"')
    if rel.cascade:
        atributos.append(f"cascade = {{{rel.cascade}}}" if "," in rel.cascade else f"cascade = {rel.cascade}")
    if rel.orphan_removal:
        atributos.append("orphanRemoval = true")

    linea = f"@{anotacion}" + (f"({', '.join(atributos)})" if atributos else "")
    lineas = [linea]
    if rel.propietaria and rel.tipo in ("manyToOne", "oneToOne"):
        lineas.append(f'@JoinColumn(name = "{rel.nombre}_id")')
    elif rel.propietaria and rel.tipo == "manyToMany":
        lineas.append(f'@JoinTable(name = "{rel.nombre}")')
    if not rel.propietaria:
        # Sin esto, Jackson serializa el ciclo bidireccional (A -> B -> A -> ...)
        # y cualquier GET que devuelva esta entidad tira StackOverflowError.
        # Se ignora el lado "mappedBy"; el lado dueño (con la FK) sí viaja en el JSON.
        # (Defensa adicional: los Controllers ya no serializan entidades
        # directamente, sólo DTOs, pero esto evita sorpresas si algo llega
        # a devolver la entidad cruda.)
        lineas.append("@JsonIgnore")
    return "\n    ".join(lineas)


def _renderizar_entidad(entidad: EntidadModelo, paquete: str) -> str:
    imports = "\n".join(f"import {i};" for i in _imports_entidad(entidad))
    extiende = f" extends {entidad.extiende}" if entidad.extiende else ""
    herencia = "@Inheritance(strategy = InheritanceType.JOINED)\n" if entidad.tiene_subclases else ""

    campos_lineas = []
    getters_setters = []

    if entidad.extiende is None:
        anotacion_id = "@GeneratedValue(strategy = GenerationType.IDENTITY)\n    " if entidad.campo_id_generado else ""
        campos_lineas.append(f"    @Id\n    {anotacion_id}private {entidad.campo_id_tipo} {entidad.campo_id_nombre};")
        getters_setters.append(_bloque_getter_setter(entidad.campo_id_nombre, entidad.campo_id_tipo))

    for campo in entidad.campos:
        valor_inicial = " = new ArrayList<>()" if campo.es_lista else ""
        campos_lineas.append(f"    private {campo.tipo_java} {campo.nombre}{valor_inicial};")
        getters_setters.append(_bloque_getter_setter(campo.nombre, campo.tipo_java))

    for rel in entidad.relaciones:
        anotacion = _campo_relacion_anotacion(rel)
        tipo_campo = f"List<{rel.entidad_relacionada}>" if rel.es_coleccion else rel.entidad_relacionada
        valor_inicial = " = new ArrayList<>()" if rel.es_coleccion else ""
        campos_lineas.append(f"    {anotacion}\n    private {tipo_campo} {rel.nombre}{valor_inicial};")
        getters_setters.append(_bloque_getter_setter(rel.nombre, tipo_campo))

    return f"""package {paquete}.model;

{imports}

@Entity
{herencia}public class {entidad.nombre_java}{extiende} {{

{chr(10).join(campos_lineas)}

    public {entidad.nombre_java}() {{
    }}

{chr(10).join(getters_setters)}
}}
"""


# --------------------------------------------------------------------------
# dto/{Entidad}DTO.java
# --------------------------------------------------------------------------


def _campo_dto_relacion(rel, entidades_por_nombre: dict[str, EntidadModelo]) -> tuple[str, str]:
    tipo_id = entidades_por_nombre[rel.entidad_relacionada].campo_id_tipo
    if rel.es_coleccion:
        return f"{rel.nombre}Ids", f"List<{tipo_id}>"
    return f"{rel.nombre}Id", tipo_id


def _asignacion_dto(nombre: str, tipo: str) -> str:
    return f"        dto.{_setter(nombre)}(entidad.{_getter(nombre, tipo)}());"


def _asignacion_entidad(nombre: str, tipo: str) -> str:
    # Usa el getter (no `this.campo` directo): si el campo viene heredado de
    # un DTO superclase, es `private` ahí y no sería visible por acceso
    # directo de campo, sólo a través de su getter público heredado.
    return f"        entidad.{_setter(nombre)}(this.{_getter(nombre, tipo)}());"


def _asignacion_dto_relacion(rel, nombre_campo: str, entidades_por_nombre: dict[str, EntidadModelo]) -> str:
    tipo_id = entidades_por_nombre[rel.entidad_relacionada].campo_id_tipo
    getter_rel = _getter(rel.nombre, rel.entidad_relacionada)
    getter_id = _getter("id", tipo_id)
    setter_dto = _setter(nombre_campo)
    if rel.es_coleccion:
        # Las colecciones de relación siempre vienen inicializadas
        # (`= new ArrayList<>()`) en la entidad, no hace falta null-check.
        return (
            f"        dto.{setter_dto}(entidad.{getter_rel}().stream()"
            f".map({rel.entidad_relacionada}::{getter_id}).collect(Collectors.toList()));"
        )
    return (
        f"        dto.{setter_dto}(entidad.{getter_rel}() != null "
        f"? entidad.{getter_rel}().{getter_id}() : null);"
    )


def _imports_dto(entidad: EntidadModelo, paquete: str) -> list[str]:
    imports = {f"{paquete}.model.{entidad.nombre_java}"}
    if any(c.es_lista for c in entidad.campos) or any(r.es_coleccion for r in entidad.relaciones):
        imports.add("java.util.List")
    if any(c.tipo_java == "LocalDate" for c in entidad.campos):
        imports.add("java.time.LocalDate")
    if any(r.es_coleccion for r in entidad.relaciones):
        imports.add("java.util.stream.Collectors")
    for rel in entidad.relaciones:
        imports.add(f"{paquete}.model.{rel.entidad_relacionada}")
    return sorted(imports)


def _renderizar_dto(entidad: EntidadModelo, paquete: str, entidades_por_nombre: dict[str, EntidadModelo]) -> str:
    imports = "\n".join(f"import {i};" for i in _imports_dto(entidad, paquete))
    extiende = f" extends {entidad.extiende}DTO" if entidad.extiende else ""

    campos_lineas = []
    getters_setters = []
    # El id siempre se copia (getter/setter heredado si esta es una
    # subclase), pero sólo se redeclara como campo en la raíz de la
    # jerarquía — mismo criterio que `_renderizar_entidad`.
    copiar_a_dto = [_asignacion_dto(entidad.campo_id_nombre, entidad.campo_id_tipo)]
    copiar_a_entidad = [_asignacion_entidad(entidad.campo_id_nombre, entidad.campo_id_tipo)]

    if entidad.extiende is None:
        campos_lineas.append(f"    private {entidad.campo_id_tipo} {entidad.campo_id_nombre};")
        getters_setters.append(_bloque_getter_setter(entidad.campo_id_nombre, entidad.campo_id_tipo))

    for campo in campos_heredados(entidad, entidades_por_nombre):
        copiar_a_dto.append(_asignacion_dto(campo.nombre, campo.tipo_java))
        copiar_a_entidad.append(_asignacion_entidad(campo.nombre, campo.tipo_java))

    for campo in entidad.campos:
        campos_lineas.append(f"    private {campo.tipo_java} {campo.nombre};")
        getters_setters.append(_bloque_getter_setter(campo.nombre, campo.tipo_java))
        copiar_a_dto.append(_asignacion_dto(campo.nombre, campo.tipo_java))
        copiar_a_entidad.append(_asignacion_entidad(campo.nombre, campo.tipo_java))

    relaciones_a_dto = []
    for rel in entidad.relaciones:
        nombre_campo, tipo_campo = _campo_dto_relacion(rel, entidades_por_nombre)
        campos_lineas.append(f"    private {tipo_campo} {nombre_campo};")
        getters_setters.append(_bloque_getter_setter(nombre_campo, tipo_campo))
        relaciones_a_dto.append(_asignacion_dto_relacion(rel, nombre_campo, entidades_por_nombre))

    cuerpo_from_entity = "\n".join(copiar_a_dto + relaciones_a_dto)

    return f"""package {paquete}.dto;

{imports}

public class {entidad.nombre_java}DTO{extiende} {{

{chr(10).join(campos_lineas)}

    public {entidad.nombre_java}DTO() {{
    }}

{chr(10).join(getters_setters)}
    public static {entidad.nombre_java}DTO fromEntity({entidad.nombre_java} entidad) {{
        {entidad.nombre_java}DTO dto = new {entidad.nombre_java}DTO();
{cuerpo_from_entity}
        return dto;
    }}

    public {entidad.nombre_java} toEntity() {{
        {entidad.nombre_java} entidad = new {entidad.nombre_java}();
{chr(10).join(copiar_a_entidad)}
        return entidad;
    }}
}}
"""


# --------------------------------------------------------------------------
# repository/{Entidad}Repository.java
# --------------------------------------------------------------------------


def _renderizar_repository(entidad: EntidadModelo, paquete: str) -> str:
    return f"""package {paquete}.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import {paquete}.model.{entidad.nombre_java};

public interface {entidad.nombre_java}Repository extends JpaRepository<{entidad.nombre_java}, {entidad.campo_id_tipo}> {{
}}
"""


# --------------------------------------------------------------------------
# service/{Entidad}Service.java
# --------------------------------------------------------------------------


def _imports_service(entidad: EntidadModelo, paquete: str) -> list[str]:
    propietarias = _relaciones_propietarias(entidad)
    imports = {
        "java.util.List",
        "java.util.stream.Collectors",
        "org.springframework.beans.factory.annotation.Autowired",
        "org.springframework.stereotype.Service",
        f"{paquete}.dto.{entidad.nombre_java}DTO",
        f"{paquete}.exception.ResourceNotFoundException",
        f"{paquete}.model.{entidad.nombre_java}",
        f"{paquete}.repository.{entidad.nombre_java}Repository",
    }
    for rel in propietarias:
        imports.add(f"{paquete}.model.{rel.entidad_relacionada}")
        imports.add(f"{paquete}.repository.{rel.entidad_relacionada}Repository")
    if any(r.es_coleccion for r in propietarias):
        imports.add("java.util.ArrayList")
    return sorted(imports)


def _linea_aplicar_relacion(rel) -> str:
    nombre_campo, _ = (f"{rel.nombre}Ids", None) if rel.es_coleccion else (f"{rel.nombre}Id", None)
    getter_dto = _getter(nombre_campo, "Long")
    if rel.es_coleccion:
        return (
            f"        if (dto.{getter_dto}() != null) {{\n"
            f"            List<{rel.entidad_relacionada}> {rel.nombre} = new ArrayList<>();\n"
            f"            {rel.nombre}Repository.findAllById(dto.{getter_dto}()).forEach({rel.nombre}::add);\n"
            f"            entidad.{_setter(rel.nombre)}({rel.nombre});\n"
            f"        }}"
        )
    return (
        f"        if (dto.{getter_dto}() != null) {{\n"
        f"            {rel.entidad_relacionada} {rel.nombre} = {rel.nombre}Repository.findById(dto.{getter_dto}())\n"
        f'                    .orElseThrow(() -> new ResourceNotFoundException("{rel.entidad_relacionada} no encontrado '
        f'con id " + dto.{getter_dto}()));\n'
        f"            entidad.{_setter(rel.nombre)}({rel.nombre});\n"
        f"        }}"
    )


def _renderizar_service(entidad: EntidadModelo, paquete: str) -> str:
    propietarias = _relaciones_propietarias(entidad)
    imports = "\n".join(f"import {i};" for i in _imports_service(entidad, paquete))

    repos_extra = "\n\n".join(
        f"    @Autowired\n    private {rel.entidad_relacionada}Repository {rel.nombre}Repository;" for rel in propietarias
    )

    metodos_stub = "\n\n".join(
        f"    public void {m.nombre}() {{\n        // TODO: implementar lógica de negocio\n    }}"
        for m in entidad.metodos
    )

    llamado_aplicar = "\n        aplicarRelaciones(entidad, dto);" if propietarias else ""

    aplicar_relaciones = ""
    if propietarias:
        lineas_aplicar = "\n".join(_linea_aplicar_relacion(rel) for rel in propietarias)
        aplicar_relaciones = (
            f"\n\n    private void aplicarRelaciones({entidad.nombre_java} entidad, {entidad.nombre_java}DTO dto) {{\n"
            f"{lineas_aplicar}\n"
            f"    }}"
        )

    return f"""package {paquete}.service;

{imports}

@Service
public class {entidad.nombre_java}Service {{

    @Autowired
    private {entidad.nombre_java}Repository repository;
{(chr(10) + chr(10) + repos_extra) if repos_extra else ""}

    public List<{entidad.nombre_java}DTO> listar() {{
        return repository.findAll().stream().map({entidad.nombre_java}DTO::fromEntity).collect(Collectors.toList());
    }}

    public {entidad.nombre_java}DTO obtenerPorId({entidad.campo_id_tipo} id) {{
        return {entidad.nombre_java}DTO.fromEntity(buscarPorId(id));
    }}

    public {entidad.nombre_java}DTO crear({entidad.nombre_java}DTO dto) {{
        {entidad.nombre_java} entidad = dto.toEntity();{llamado_aplicar}
        return {entidad.nombre_java}DTO.fromEntity(repository.save(entidad));
    }}

    public {entidad.nombre_java}DTO actualizar({entidad.campo_id_tipo} id, {entidad.nombre_java}DTO dto) {{
        buscarPorId(id);
        {entidad.nombre_java} entidad = dto.toEntity();
        entidad.{_setter(entidad.campo_id_nombre)}(id);{llamado_aplicar}
        return {entidad.nombre_java}DTO.fromEntity(repository.save(entidad));
    }}

    public void eliminar({entidad.campo_id_tipo} id) {{
        buscarPorId(id);
        repository.deleteById(id);
    }}

    private {entidad.nombre_java} buscarPorId({entidad.campo_id_tipo} id) {{
        return repository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("{entidad.nombre_java} no encontrado con id " + id));
    }}
{(chr(10) + chr(10) + metodos_stub) if metodos_stub else ""}{aplicar_relaciones}
}}
"""


# --------------------------------------------------------------------------
# controller/{Entidad}Controller.java
# --------------------------------------------------------------------------


def _renderizar_controller(entidad: EntidadModelo, paquete: str) -> str:
    return f"""package {paquete}.controller;

import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import {paquete}.dto.{entidad.nombre_java}DTO;
import {paquete}.service.{entidad.nombre_java}Service;

@RestController
@RequestMapping("/api/{entidad.endpoint}")
public class {entidad.nombre_java}Controller {{

    @Autowired
    private {entidad.nombre_java}Service service;

    @GetMapping
    public List<{entidad.nombre_java}DTO> listar() {{
        return service.listar();
    }}

    @GetMapping("/{{id}}")
    public {entidad.nombre_java}DTO obtenerPorId(@PathVariable {entidad.campo_id_tipo} id) {{
        return service.obtenerPorId(id);
    }}

    @PostMapping
    public {entidad.nombre_java}DTO crear(@RequestBody {entidad.nombre_java}DTO dto) {{
        return service.crear(dto);
    }}

    @PutMapping("/{{id}}")
    public {entidad.nombre_java}DTO actualizar(@PathVariable {entidad.campo_id_tipo} id, @RequestBody {entidad.nombre_java}DTO dto) {{
        return service.actualizar(id, dto);
    }}

    @DeleteMapping("/{{id}}")
    public ResponseEntity<Void> eliminar(@PathVariable {entidad.campo_id_tipo} id) {{
        service.eliminar(id);
        return ResponseEntity.noContent().build();
    }}
}}
"""


# --------------------------------------------------------------------------
# config/CorsConfig.java — una vez por proyecto
# --------------------------------------------------------------------------


def _cors_config(paquete: str) -> str:
    return f"""package {paquete}.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class CorsConfig implements WebMvcConfigurer {{

    @Override
    public void addCorsMappings(CorsRegistry registry) {{
        registry.addMapping("/api/**")
                .allowedOrigins("*")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS");
    }}
}}
"""


# --------------------------------------------------------------------------
# exception/* — manejo global de errores, una vez por proyecto
# --------------------------------------------------------------------------


def _resource_not_found_exception(paquete: str) -> str:
    return f"""package {paquete}.exception;

public class ResourceNotFoundException extends RuntimeException {{

    public ResourceNotFoundException(String mensaje) {{
        super(mensaje);
    }}
}}
"""


def _error_response(paquete: str) -> str:
    return f"""package {paquete}.exception;

import java.time.LocalDateTime;

public record ErrorResponse(LocalDateTime timestamp, int status, String error, String message, String path) {{
}}
"""


def _global_exception_handler(paquete: str) -> str:
    return f"""package {paquete}.exception;

import jakarta.servlet.http.HttpServletRequest;
import java.time.LocalDateTime;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {{

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> manejarNoEncontrado(ResourceNotFoundException ex, HttpServletRequest request) {{
        ErrorResponse error = new ErrorResponse(
                LocalDateTime.now(), HttpStatus.NOT_FOUND.value(), "Not Found", ex.getMessage(), request.getRequestURI());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
    }}

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> manejarError(Exception ex, HttpServletRequest request) {{
        ErrorResponse error = new ErrorResponse(
                LocalDateTime.now(), HttpStatus.INTERNAL_SERVER_ERROR.value(), "Internal Server Error",
                "Ocurrió un error inesperado.", request.getRequestURI());
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
    }}
}}
"""


# --------------------------------------------------------------------------
# Resto del proyecto (pom.xml, application.properties, main class, README)
# --------------------------------------------------------------------------


def _pom_xml(paquete: str, artefacto: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.5</version>
        <relativePath/>
    </parent>

    <groupId>{paquete}</groupId>
    <artifactId>{artefacto}</artifactId>
    <version>0.0.1-SNAPSHOT</version>
    <name>{artefacto}</name>
    <description>Backend generado automáticamente a partir de un diagrama de clases UML</description>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
"""


def _application_properties() -> str:
    return """# Generado automáticamente. Por defecto usa H2 en memoria: no hace falta
# instalar ni configurar nada para correr el backend (los datos se pierden
# al reiniciar). Para usar PostgreSQL en su lugar (igual que el proyecto
# original), comentá el bloque H2 y descomentá el bloque Postgres.

spring.datasource.url=jdbc:h2:mem:appdb
spring.datasource.driver-class-name=org.h2.Driver
spring.datasource.username=sa
spring.datasource.password=
spring.h2.console.enabled=true
spring.jpa.hibernate.ddl-auto=update
spring.jpa.show-sql=true

# spring.datasource.url=jdbc:postgresql://localhost:5432/nombre_db
# spring.datasource.driver-class-name=org.postgresql.Driver
# spring.datasource.username=postgres
# spring.datasource.password=postgres
# spring.jpa.hibernate.ddl-auto=update
"""


def _application_java(paquete: str, artefacto: str) -> str:
    clase = f"{artefacto[:1].upper()}{artefacto[1:]}Application"
    return f"""package {paquete};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class {clase} {{

    public static void main(String[] args) {{
        SpringApplication.run({clase}.class, args);
    }}
}}
""", clase


def _readme(artefacto: str, entidades: list[EntidadModelo]) -> str:
    endpoints = "\n".join(f"- `/api/{e.endpoint}` — CRUD de `{e.nombre_java}`" for e in entidades)
    return f"""# {artefacto}

Backend generado automáticamente a partir de un diagrama de clases UML.

## Cómo correrlo

```
mvn spring-boot:run
```

Por defecto usa una base H2 en memoria (sin configuración previa). La API queda en `http://localhost:8080`.
CORS está habilitado para `/api/**` desde cualquier origen, así que también se puede probar directo desde un navegador o desde el frontend generado.

## Endpoints generados

{endpoints}

Cada endpoint expone y recibe DTOs (paquete `dto/`), no las entidades JPA directamente, para evitar loops de serialización en relaciones bidireccionales. Los errores (recurso no encontrado, errores inesperados) devuelven un JSON estructurado (`timestamp`, `status`, `error`, `message`, `path`).
"""


def generar_zip_backend(contenido: dict, nombre_proyecto: str) -> bytes:
    modelo: ModeloBackend = construir_modelo_backend(contenido, nombre_proyecto)
    artefacto = modelo.paquete.rsplit(".", 1)[-1]
    base_java = "src/main/java/" + modelo.paquete.replace(".", "/")
    entidades_por_nombre = {e.nombre_java: e for e in modelo.entidades}

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("pom.xml", _pom_xml(modelo.paquete, artefacto))
        zip_file.writestr("src/main/resources/application.properties", _application_properties())
        zip_file.writestr("README.md", _readme(artefacto, modelo.entidades))

        contenido_app, clase_app = _application_java(modelo.paquete, artefacto)
        zip_file.writestr(f"{base_java}/{clase_app}.java", contenido_app)

        zip_file.writestr(f"{base_java}/config/CorsConfig.java", _cors_config(modelo.paquete))
        zip_file.writestr(
            f"{base_java}/exception/ResourceNotFoundException.java", _resource_not_found_exception(modelo.paquete)
        )
        zip_file.writestr(f"{base_java}/exception/ErrorResponse.java", _error_response(modelo.paquete))
        zip_file.writestr(
            f"{base_java}/exception/GlobalExceptionHandler.java", _global_exception_handler(modelo.paquete)
        )

        for entidad in modelo.entidades:
            zip_file.writestr(f"{base_java}/model/{entidad.nombre_java}.java", _renderizar_entidad(entidad, modelo.paquete))
            zip_file.writestr(
                f"{base_java}/dto/{entidad.nombre_java}DTO.java",
                _renderizar_dto(entidad, modelo.paquete, entidades_por_nombre),
            )
            zip_file.writestr(
                f"{base_java}/repository/{entidad.nombre_java}Repository.java",
                _renderizar_repository(entidad, modelo.paquete),
            )
            zip_file.writestr(
                f"{base_java}/service/{entidad.nombre_java}Service.java", _renderizar_service(entidad, modelo.paquete)
            )
            zip_file.writestr(
                f"{base_java}/controller/{entidad.nombre_java}Controller.java",
                _renderizar_controller(entidad, modelo.paquete),
            )

    return buffer.getvalue()
