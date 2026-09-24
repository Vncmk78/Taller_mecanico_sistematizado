"""Documentación OpenAPI/Swagger de la API Gateway.

El proxy reenvía `/api/*` sin conocer los contratos, por eso el Swagger por
defecto solo mostraría `/`, `/api/health` y un `/api/{ruta}` genérico. Aquí se
reescribe el `openapi.json` que expone la app (`app.openapi`) para documentar
los 7 endpoints reales que enruta la Gateway hacia MS1 (Autenticación) y MS2
(Vehículos), con sus esquemas (`gateway/contratos`), la seguridad `bearerAuth`
y el formato común de errores de la Gateway (`gateway.esquemas`).

Los endpoints que todavía no existen en los microservicios (órdenes,
presupuestos, evidencias) no se documentan: aparecen como pendientes en
`docs/contratos-api-gateway.md`.
"""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from gateway.contratos import auth as contratos_auth
from gateway.contratos import vehiculos as contratos_vehiculos
from gateway.esquemas import DetalleError, ErrorRespuesta

_TITULO = "SGTM — API Gateway"
_VERSION = "0.1.0"
_DESCRIPCION = (
    "Único punto de entrada del backend del SGTM (taller mecánico). "
    "Documenta los endpoints reales que la Gateway enruta hacia MS1 "
    "(Autenticación y Usuarios) y MS2 (Vehículos y Órdenes). Los errores "
    "propios de la Gateway usan el esquema `ErrorRespuesta`; los errores de "
    "los microservicios pasan sin modificarse. "
    "La cabecera opcional `X-Request-ID` permite rastrear una petición."
)

_TAGS = [
    {
        "name": "Autenticación",
        "description": "Registro, login y usuario actual (MS1).",
    },
    {
        "name": "Vehículos",
        "description": "Registro, consulta y actualización de vehículos (MS2).",
    },
    {
        "name": "Gateway",
        "description": "Endpoints propios de la Gateway (índice y healthcheck).",
    },
]

_CONTRATOS: list[tuple[str, type[BaseModel]]] = [
    ("RegistroSolicitud", contratos_auth.RegistroSolicitud),
    ("LoginSolicitud", contratos_auth.LoginSolicitud),
    ("UsuarioRespuesta", contratos_auth.UsuarioRespuesta),
    ("TokenRespuesta", contratos_auth.TokenRespuesta),
    ("VehiculoCrear", contratos_vehiculos.VehiculoCrear),
    ("VehiculoActualizar", contratos_vehiculos.VehiculoActualizar),
    ("VehiculoRespuesta", contratos_vehiculos.VehiculoRespuesta),
]

_PARAMETRO_X_REQUEST_ID: dict[str, object] = {
    "name": "X-Request-ID",
    "in": "header",
    "required": False,
    "description": (
        "Identificador opcional para rastrear la petición (letras, números "
        "o guiones, hasta 128 caracteres). Si no viene o es inválido, la "
        "Gateway genera un UUID."
    ),
    "schema": {
        "type": "string",
        "maxLength": 128,
        "pattern": "^[A-Za-z0-9-]{1,128}$",
        "example": "abc-123",
    },
}

_PARAMETRO_VEHICULO_ID: dict[str, object] = {
    "name": "vehiculo_id",
    "in": "path",
    "required": True,
    "description": "Identificador del vehículo.",
    "schema": {"type": "integer", "format": "int64", "example": 12},
}


def _ref(nombre: str) -> dict[str, object]:
    return {"$ref": f"#/components/schemas/{nombre}"}


def _respuesta(descripcion: str, esquema: dict[str, object]) -> dict[str, object]:
    return {
        "description": descripcion,
        "content": {"application/json": {"schema": esquema}},
    }


def _respuesta_detalle_ms(descripcion: str) -> dict[str, object]:
    """Error generado por un microservicio: pasa tal cual (`{"detail": "..."}`)."""
    return _respuesta(descripcion, _ref("ErrorDetalle"))


def _operacion(
    *,
    tag: str,
    resumen: str,
    descripcion: str,
    operation_id: str,
    cuerpo: str | None,
    respuestas_ok: dict[str, dict[str, object]],
    errores_ms: dict[str, str] | None = None,
    requiere_auth: bool,
    con_vehiculo_id: bool = False,
    descripcion_404: str = (
        "Ruta no encontrada en la Gateway (RUTA_NO_ENCONTRADA)."
    ),
    esquema_404: dict[str, object] | None = None,
) -> dict[str, object]:
    parametros: list[dict[str, object]] = [_PARAMETRO_X_REQUEST_ID]
    if con_vehiculo_id:
        parametros.append(_PARAMETRO_VEHICULO_ID)

    errores: dict[str, dict[str, object]] = {
        **{
            str(estado): _respuesta_detalle_ms(descripcion)
            for estado, descripcion in (errores_ms or {}).items()
        },
        "404": _respuesta(
            descripcion_404,
            esquema_404 if esquema_404 is not None else _ref("ErrorRespuesta"),
        ),
        "502": _respuesta(
            "Microservicio no disponible (MICROSERVICIO_INALCANZABLE).",
            _ref("ErrorRespuesta"),
        ),
        "500": _respuesta(
            "Error no controlado de la Gateway (ERROR_INTERNO).",
            _ref("ErrorRespuesta"),
        ),
    }

    operacion: dict[str, object] = {
        "tags": [tag],
        "summary": resumen,
        "description": descripcion,
        "operationId": operation_id,
        "parameters": parametros,
        "responses": {**respuestas_ok, **errores},
        "security": [{"bearerAuth": []}] if requiere_auth else [],
    }
    if cuerpo is not None:
        operacion["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": _ref(cuerpo)}},
        }
    return operacion


def _caminos_documentados() -> dict[str, dict[str, object]]:
    # El 404 de un vehículo puede venir del microservicio (Vehículo no
    # encontrado, {"detail": ...}) o de la Gateway (RUTA_NO_ENCONTRADA).
    error_404_vehiculo: dict[str, object] = {
        "oneOf": [_ref("ErrorRespuesta"), _ref("ErrorDetalle")],
    }

    return {
        "/api/auth/register": {
            "post": _operacion(
                tag="Autenticación",
                resumen="Registrar cliente",
                descripcion=(
                    "Crea una cuenta con rol Cliente, asignado en el servidor. "
                    "No requiere autenticación."
                ),
                operation_id="registrar_cliente",
                cuerpo="RegistroSolicitud",
                respuestas_ok={
                    "201": _respuesta("Usuario registrado.", _ref("UsuarioRespuesta"))
                },
                errores_ms={
                    "409": "El correo ya está registrado",
                    "422": "Datos inválidos",
                },
                requiere_auth=False,
            )
        },
        "/api/auth/login": {
            "post": _operacion(
                tag="Autenticación",
                resumen="Iniciar sesión",
                descripcion=(
                    "Valida credenciales y devuelve el token de acceso. "
                    "No requiere autenticación."
                ),
                operation_id="iniciar_sesion",
                cuerpo="LoginSolicitud",
                respuestas_ok={
                    "200": _respuesta("Token de acceso y usuario.", _ref("TokenRespuesta"))
                },
                errores_ms={"401": "Credenciales inválidas"},
                requiere_auth=False,
            )
        },
        "/api/auth/me": {
            "get": _operacion(
                tag="Autenticación",
                resumen="Usuario actual",
                descripcion="Devuelve el usuario identificado por el token.",
                operation_id="usuario_actual",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta("Usuario autenticado.", _ref("UsuarioRespuesta"))
                },
                errores_ms={"401": "JWT ausente o inválido"},
                requiere_auth=True,
            )
        },
        "/api/vehiculos": {
            "post": _operacion(
                tag="Vehículos",
                resumen="Registrar un vehículo",
                descripcion="Registra un vehículo para el cliente autenticado.",
                operation_id="registrar_vehiculo",
                cuerpo="VehiculoCrear",
                respuestas_ok={
                    "201": _respuesta("Vehículo registrado.", _ref("VehiculoRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Cliente",
                    "409": "La patente ya está registrada",
                    "422": "Datos inválidos",
                },
                requiere_auth=True,
            ),
            "get": _operacion(
                tag="Vehículos",
                resumen="Listar vehículos",
                descripcion="Lista los vehículos registrados del cliente autenticado.",
                operation_id="listar_vehiculos",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta(
                        "Lista de vehículos.",
                        {"type": "array", "items": _ref("VehiculoRespuesta")},
                    )
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Cliente",
                },
                requiere_auth=True,
            ),
        },
        "/api/vehiculos/{vehiculo_id}": {
            "get": _operacion(
                tag="Vehículos",
                resumen="Consultar un vehículo",
                descripcion="Devuelve un vehículo del cliente autenticado.",
                operation_id="consultar_vehiculo",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta("Vehículo encontrado.", _ref("VehiculoRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Cliente",
                },
                requiere_auth=True,
                con_vehiculo_id=True,
                descripcion_404=(
                    "No encontrado. Si el vehículo no existe, el microservicio "
                    "responde {'detail': 'Vehículo no encontrado'}."
                ),
                esquema_404=error_404_vehiculo,
            ),
            "patch": _operacion(
                tag="Vehículos",
                resumen="Actualizar parcialmente un vehículo",
                descripcion=(
                    "Modifica uno o más campos de un vehículo del cliente "
                    "autenticado (enviar al menos uno)."
                ),
                operation_id="actualizar_vehiculo",
                cuerpo="VehiculoActualizar",
                respuestas_ok={
                    "200": _respuesta("Vehículo actualizado.", _ref("VehiculoRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Cliente",
                    "422": "Datos inválidos",
                },
                requiere_auth=True,
                con_vehiculo_id=True,
                descripcion_404=(
                    "No encontrado. Si el vehículo no existe, el microservicio "
                    "responde {'detail': 'Vehículo no encontrado'}."
                ),
                esquema_404=error_404_vehiculo,
            ),
        },
    }


def _esquemas_documentados() -> dict[str, dict[str, object]]:
    esquemas: dict[str, dict[str, object]] = {
        nombre: modelo.model_json_schema(ref_template="#/components/schemas/{model}")
        for nombre, modelo in _CONTRATOS
    }
    esquemas["ErrorRespuesta"] = ErrorRespuesta.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    esquemas["DetalleError"] = DetalleError.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    esquemas["ErrorDetalle"] = {
        "type": "object",
        "properties": {
            # Los errores de validación de FastAPI (422) ponen una lista de
            # errores en detail, no un string.
            "detail": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "object"}},
                ]
            }
        },
        "required": ["detail"],
    }
    return esquemas


def construir_openapi(app: FastAPI) -> dict[str, object]:
    """Arma el esquema OpenAPI de la Gateway con los contratos documentados.

    Parte del esquema autogenerado por FastAPI (índice y healthcheck) y le
    agrega los 7 endpoints de negocio, la seguridad `bearerAuth` y los
    esquemas de `gateway/contratos` y `gateway/esquemas`.
    """
    if getattr(app, "openapi_schema", None) is not None:
        return app.openapi_schema

    esquema = get_openapi(
        title=_TITULO,
        version=_VERSION,
        description=_DESCRIPCION,
        routes=app.routes,
        tags=_TAGS,
    )
    esquema["paths"] = {**esquema["paths"], **_caminos_documentados()}

    componentes = esquema.setdefault("components", {})
    componentes["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    componentes["schemas"] = {
        **componentes.get("schemas", {}),
        **_esquemas_documentados(),
    }

    app.openapi_schema = esquema
    return esquema