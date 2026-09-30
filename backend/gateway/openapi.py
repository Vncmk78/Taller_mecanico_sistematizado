"""Documentación OpenAPI/Swagger de la API Gateway.

El proxy reenvía `/api/*` sin conocer los contratos, por eso el Swagger por
defecto solo mostraría `/`, `/api/health` y un `/api/{ruta}` genérico. Aquí se
reescribe el `openapi.json` que expone la app (`app.openapi`) para documentar
los 11 endpoints reales que enruta la Gateway hacia MS1 (Autenticación) y MS2
(Vehículos y Órdenes), con sus esquemas (`gateway/contratos`), la seguridad
`bearerAuth` y el formato común de errores de la Gateway (`gateway.esquemas`).

Los endpoints todavía no implementados (presupuestos, evidencias, historial
consultable y cambio general de estado) no se publican como contratos.
"""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from gateway.contratos import auth as contratos_auth
from gateway.contratos import ordenes as contratos_ordenes
from gateway.contratos import vehiculos as contratos_vehiculos
from gateway.esquemas import DetalleError, ErrorRespuesta
from gateway.openapi_ejemplos import agregar_ejemplos_gateway
from shared.openapi_ordenes import agregar_ejemplos_ordenes

_TITULO = "SGTM — API Gateway"
_VERSION = "0.1.0"
_DESCRIPCION = """Único punto de entrada del backend del SGTM (taller mecánico). \
Documenta los endpoints reales que la Gateway enruta hacia MS1 (Autenticación y \
Usuarios) y MS2 (Vehículos y Órdenes).

## URL base

La URL base es el origen donde esté desplegada la Gateway. Todos los endpoints de \
negocio cuelgan de `/api` y se reenvían a los microservicios sin modificar el \
body, el query string ni la cabecera `Authorization`.

## Autenticación

1. `POST /api/auth/register` crea una cuenta con rol Cliente (el rol lo asigna el \
servidor, nunca el body).
2. `POST /api/auth/login` devuelve `access_token` y `token_type: bearer`.
3. Se envía en cada llamada protegida: `Authorization: Bearer <access_token>`.

El botón **Authorize** de Swagger completa esa cabecera por ti. La Gateway no \
valida el JWT: lo reenvía al microservicio, que responde `401` si falta o expira \
y `403` si el rol no corresponde. Ante un `401` el frontend debe limpiar la sesión \
y volver a iniciar sesión; un `403` significa que el usuario está identificado pero \
no tiene permisos.

## Formato de errores

- Errores de la Gateway: `ErrorRespuesta`, \
`{"detail": "...", "error": {"codigo", "estado", "ruta", "request_id"}}`.
- Errores de los microservicios: `ErrorDetalle`, `{"detail": "..."}`. En un `422` \
de validación, `detail` es una lista de errores de Pydantic.

| Estado | Código de la Gateway | Cuándo ocurre |
|---|---|---|
| 404 | `RUTA_NO_ENCONTRADA` | La ruta no existe |
| 405 | `METODO_NO_PERMITIDO` | El método no existe en esa ruta |
| 500 | `ERROR_INTERNO` o `ERROR_MICROSERVICIO` | Error no controlado o respuesta no JSON |
| 502 | `MICROSERVICIO_INALCANZABLE` | El microservicio no respondió |
| 503 | `GATEWAY_SATURADA` | El pool de conexiones está agotado |
| 504 | `TIEMPO_AGOTADO` | El microservicio tardó demasiado |

Las respuestas `401`, `500`, `502`, `503` y `504` también están publicadas como \
respuestas reutilizables en `components.responses`.

## X-Request-ID

Se puede enviar `X-Request-ID` (letras, números y guiones) para rastrear una \
petición; si no llega o es inválida, la Gateway genera un UUID y lo devuelve en la \
respuesta. Es la misma clave que aparece en `error.request_id`.

El detalle completo de los contratos está en `docs/contratos-api-gateway.md`."""

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
        "name": "Órdenes",
        "description": "Creación, consulta y asignación inicial de órdenes (MS2).",
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
    ("OrdenCrear", contratos_ordenes.OrdenCrear),
    (
        "AsignacionMecanicoActualizar",
        contratos_ordenes.AsignacionMecanicoActualizar,
    ),
    ("OrdenRespuesta", contratos_ordenes.OrdenRespuesta),
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

_PARAMETRO_ORDEN_ID: dict[str, object] = {
    "name": "orden_id",
    "in": "path",
    "required": True,
    "description": "Identificador de la orden de trabajo.",
    "schema": {"type": "integer", "format": "int64", "example": 31},
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
    con_orden_id: bool = False,
    descripcion_404: str = (
        "Ruta no encontrada en la Gateway (RUTA_NO_ENCONTRADA)."
    ),
    esquema_404: dict[str, object] | None = None,
) -> dict[str, object]:
    parametros: list[dict[str, object]] = [_PARAMETRO_X_REQUEST_ID]
    if con_vehiculo_id:
        parametros.append(_PARAMETRO_VEHICULO_ID)
    if con_orden_id:
        parametros.append(_PARAMETRO_ORDEN_ID)

    errores: dict[str, dict[str, object]] = {
        **{
            str(estado): _respuesta_detalle_ms(descripcion)
            for estado, descripcion in (errores_ms or {}).items()
        },
        "404": _respuesta(
            descripcion_404,
            esquema_404 if esquema_404 is not None else _ref("ErrorRespuesta"),
        ),
        # El 401 de cada microservicio, el 500 (que puede ser de la Gateway o del
        # servicio) y el 502 se dejan escritos en línea: `tests/test_gateway_openapi.py`
        # verifica que esas respuestas distingan el esquema propio del de cada
        # microservicio. Los 503 y 504 sí son idénticos en todas las operaciones y
        # se referencian desde `components.responses`.
        "502": _respuesta(
            "Microservicio no disponible (MICROSERVICIO_INALCANZABLE).",
            _ref("ErrorRespuesta"),
        ),
        "500": _respuesta(
            (
                "Error interno. Puede provenir del microservicio con "
                "ErrorDetalle o de la Gateway con ERROR_INTERNO."
            ),
            {"oneOf": [_ref("ErrorRespuesta"), _ref("ErrorDetalle")]},
        ),
        "503": {"$ref": "#/components/responses/GatewaySaturada"},
        "504": {"$ref": "#/components/responses/TiempoAgotado"},
    }

    # MS1 y MS2 acompañan el 401 con `WWW-Authenticate: Bearer` y la Gateway lo
    # reenvía; se documenta en cada operación protegida.
    if requiere_auth and "401" in errores:
        errores["401"]["headers"] = {
            "WWW-Authenticate": {
                "description": "Esquema de autenticación esperado.",
                "schema": {"type": "string", "example": "Bearer"},
            }
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
    # Un recurso ausente lo informa MS2 con {"detail": ...}; la Gateway
    # conserva además su formato propio para errores que ella genera.
    error_404_recurso: dict[str, object] = {
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
                descripcion=(
                    "Registra un vehículo para el cliente autenticado. La patente "
                    "es obligatoria, no vacía y única; no se impone un formato ni "
                    "un largo funcional específico."
                ),
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
                descripcion_404="No existe el perfil Cliente local en MS2.",
                esquema_404=error_404_recurso,
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
                descripcion_404="No existe el perfil Cliente local en MS2.",
                esquema_404=error_404_recurso,
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
                esquema_404=error_404_recurso,
            ),
            "patch": _operacion(
                tag="Vehículos",
                resumen="Actualizar parcialmente un vehículo",
                descripcion=(
                    "Modifica uno o más campos de un vehículo del cliente "
                    "autenticado (enviar al menos uno). La patente y el "
                    "propietario son inmutables."
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
                esquema_404=error_404_recurso,
            ),
        },
        "/api/ordenes": {
            "post": _operacion(
                tag="Órdenes",
                resumen="Crear una orden de trabajo",
                descripcion=(
                    "Solo un Administrador crea la orden para un vehículo "
                    "registrado. Se asocia o crea el ingreso físico, la orden "
                    "comienza en Recibido y puede quedar sin mecánico."
                ),
                operation_id="crear_orden",
                cuerpo="OrdenCrear",
                respuestas_ok={
                    "201": _respuesta("Orden creada.", _ref("OrdenRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador",
                    "422": "Datos inválidos",
                },
                requiere_auth=True,
                descripcion_404="Vehículo no encontrado.",
                esquema_404=error_404_recurso,
            ),
            "get": _operacion(
                tag="Órdenes",
                resumen="Listar órdenes visibles",
                descripcion=(
                    "Administrador ve todas; Cliente ve las asociadas a sus "
                    "vehículos; Mecánico ve las que tiene asignadas. En un "
                    "usuario multirol se unen sus alcances, y Administrador "
                    "mantiene visibilidad global."
                ),
                operation_id="listar_ordenes",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta(
                        "Lista de órdenes visibles.",
                        {"type": "array", "items": _ref("OrdenRespuesta")},
                    )
                },
                errores_ms={"401": "JWT ausente o inválido"},
                requiere_auth=True,
            ),
        },
        "/api/ordenes/{orden_id}": {
            "get": _operacion(
                tag="Órdenes",
                resumen="Consultar una orden visible",
                descripcion=(
                    "Aplica la misma visibilidad del listado. Una orden "
                    "inexistente o ajena responde 404 sin revelar su existencia."
                ),
                operation_id="consultar_orden",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta("Orden encontrada.", _ref("OrdenRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "422": "Identificador de orden inválido",
                },
                requiere_auth=True,
                con_orden_id=True,
                descripcion_404="Orden inexistente o no visible.",
                esquema_404=error_404_recurso,
            )
        },
        "/api/ordenes/{orden_id}/mecanico": {
            "put": _operacion(
                tag="Órdenes",
                resumen="Asignar o reasignar el mecánico responsable",
                descripcion=(
                    "Solo un Administrador asigna o reasigna. La primera "
                    "asignación cambia Recibido a Esperando diagnóstico y "
                    "registra los historiales de asignación y estado. Una "
                    "reasignación conserva el estado; Entregado y Cancelado "
                    "rechazan la operación."
                ),
                operation_id="asignar_mecanico",
                cuerpo="AsignacionMecanicoActualizar",
                respuestas_ok={
                    "200": _respuesta("Responsable actualizado.", _ref("OrdenRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador",
                    "409": "Autoasignación o estado terminal",
                    "422": "Datos inválidos",
                },
                requiere_auth=True,
                con_orden_id=True,
                descripcion_404="Orden no encontrada.",
                esquema_404=error_404_recurso,
            )
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
    agrega los 11 endpoints de negocio, la seguridad `bearerAuth` y los
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

    agregar_ejemplos_ordenes(esquema, prefijo="/api")
    agregar_ejemplos_gateway(esquema)
    app.openapi_schema = esquema
    return esquema
