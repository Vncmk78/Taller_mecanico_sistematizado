"""Documentación OpenAPI/Swagger de la API Gateway.

El proxy reenvía `/api/*` sin conocer los contratos, por eso el Swagger por
defecto solo mostraría `/`, `/api/health` y un `/api/{ruta}` genérico. Aquí se
reescribe el `openapi.json` que expone la app (`app.openapi`) para documentar
los endpoints reales que enruta la Gateway hacia los cuatro microservicios:
MS1 (Autenticación y Usuarios), MS2 (Vehículos y Órdenes), MS3 (Presupuestos,
Repuestos, Proveedores e Inventario, en `gateway/openapi_ms3.py`) y MS4
(Evidencias), con sus esquemas (`gateway/contratos`), la seguridad `bearerAuth`
y el formato común de errores de la Gateway (`gateway.esquemas`).

`tests/test_gateway_openapi.py` compara este documento con el OpenAPI real de
los cuatro servicios: un endpoint nuevo sin documentar hace fallar la prueba.
"""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from gateway.contratos import auth as contratos_auth
from gateway.contratos import evidencias as contratos_evidencias
from gateway.contratos import inventario as contratos_inventario
from gateway.contratos import ordenes as contratos_ordenes
from gateway.contratos import vehiculos as contratos_vehiculos
from gateway.esquemas import DetalleError, ErrorRespuesta
from gateway.openapi_ejemplos import agregar_ejemplos_gateway
from shared.openapi_ordenes import agregar_ejemplos_ordenes
from shared.contratos_decisiones import (
    AplicacionDecisionRespuesta, DecisionAplicacionPendiente,
    DecisionOrdenSolicitud, DecisionPresupuestoVerificada,
    EnvioPresupuestoSolicitud,
)

_TITULO = "SGTM — API Gateway"
_VERSION = "2.0.1"
_DESCRIPCION = """Único punto de entrada del backend del SGTM (taller mecánico). \
Documenta los endpoints reales que la Gateway enruta hacia los cuatro \
microservicios: MS1 (Autenticación y Usuarios), MS2 (Vehículos y Órdenes), MS3 \
(Presupuestos, Repuestos, Proveedores e Inventario) y MS4 (Evidencias multimedia).

| Prefijo | Microservicio |
|---|---|
| `/api/auth` | MS1 — Autenticación y Usuarios |
| `/api/vehiculos`, `/api/ordenes` | MS2 — Vehículos y Órdenes de Trabajo |
| `/api/presupuestos`, `/api/repuestos`, `/api/proveedores`, `/api/inventario` | MS3 — Presupuestos e Inventario |
| `/api/evidencias` | MS4 — Evidencia Multimedia |

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
| 413 | `CUERPO_DEMASIADO_GRANDE` | El body supera el límite (1 MiB; 12 MiB en `/api/evidencias`) |
| 500 | `ERROR_INTERNO` o `ERROR_MICROSERVICIO` | Error no controlado o respuesta no JSON |
| 502 | `MICROSERVICIO_INALCANZABLE` | El microservicio no respondió |
| 503 | `GATEWAY_SATURADA` | El pool de conexiones está agotado |
| 504 | `TIEMPO_AGOTADO` | El microservicio tardó demasiado |

Las respuestas `401`, `500`, `502`, `503` y `504` también están publicadas como \
respuestas reutilizables en `components.responses`.

Los errores de la Gateway llevan `Cache-Control: no-store`, y los `502`, `503` y \
`504` además `Retry-After` (segundos). Web y móvil solo deben reintentar \
automáticamente un `GET`, como máximo 2 veces, respetando esa espera; nunca un \
`POST`, `PUT` o `PATCH` (las escrituras de MS3 tienen su propia ruta de \
reintento idempotente).

## X-Request-ID

Se puede enviar `X-Request-ID` (letras, números y guiones) para rastrear una \
petición; si no llega o es inválida, la Gateway genera un UUID y lo devuelve en la \
respuesta. Es la misma clave que aparece en `error.request_id`.

## Versión del contrato

`info.version` sigue versionado semántico. **1.0.0 es la primera versión \
estable** para integración (frontend web y app móvil de Integración IV); su copia \
congelada está en `backend/docs/openapi/sgtm-gateway-1.0.0.json`.

- **PATCH** (1.0.x): descripciones, ejemplos o estados de error que ya respondía \
el servicio y faltaban documentar.
- **MINOR** (1.x.0): operaciones, campos opcionales o valores nuevos; ningún \
cliente existente se rompe.
- **MAJOR** (2.0.0): quitar o renombrar rutas o campos, volver obligatorio un \
campo, cambiar tipos o el significado de un estado.

El historial de cambios y la política completa están en \
`docs/versionado-contrato-openapi.md`.

El detalle completo de los contratos está en `docs/contratos-api-gateway.md`."""

_DESCRIPCION += (
    f"\n\nVersión vigente: **{_VERSION}**. Copia congelada: "
    f"`backend/docs/openapi/sgtm-gateway-{_VERSION}.json`."
)

_TAGS = [
    {
        "name": "Autenticación",
        "description": "Registro, login y usuario actual (MS1).",
    },
    {
        "name": "Usuarios",
        "description": (
            "Consulta de cuentas y asignación o retiro de roles restringidos "
            "(MS1, solo Administrador)."
        ),
    },
    {
        "name": "Vehículos",
        "description": (
            "Registro, consulta por rol y actualización de vehículos (MS2)."
        ),
    },
    {
        "name": "Órdenes",
        "description": (
            "Creación, consulta, historial, bitácora de trabajo, cambio de "
            "estado, asignación inicial, entrega física y solicitudes de "
            "cancelación con revisión administrativa (MS2)."
        ),
    },
    {
        "name": "Evidencias",
        "description": (
            "Subida de fotos y videos de una orden, consulta por rol y "
            "descarga con URL prefirmada de corta duración (MS4)."
        ),
    },
    {
        "name": "Notificaciones",
        "description": "Bandeja personal de notificaciones (MS1).",
    },
    {
        "name": "Presupuestos",
        "description": (
            "Presupuesto único por orden con versiones inmutables una vez "
            "enviadas, ítems, envío al cliente, decisión y coordinación con "
            "MS2 (MS3)."
        ),
    },
    {
        "name": "Repuestos",
        "description": (
            "Catálogo de repuestos, umbral particular y trazabilidad "
            "repuesto–proveedor (MS3)."
        ),
    },
    {
        "name": "Proveedores",
        "description": "Proveedores (distribuidores) de repuestos y su trazabilidad (MS3).",
    },
    {
        "name": "Inventario",
        "description": (
            "Movimientos de stock idempotentes, disponibilidad, reservas, "
            "consumos y alertas de stock bajo (MS3)."
        ),
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
    ("NotificacionRespuesta", contratos_auth.NotificacionRespuesta),
    ("RepuestoReservado", contratos_inventario.RepuestoReservado),
    (
        "DisponibilidadRepuestosRespuesta",
        contratos_inventario.DisponibilidadRepuestosRespuesta,
    ),
    ("RolAsignarSolicitud", contratos_auth.RolAsignarSolicitud),
    ("VehiculoCrear", contratos_vehiculos.VehiculoCrear),
    ("VehiculoActualizar", contratos_vehiculos.VehiculoActualizar),
    ("VehiculoRespuesta", contratos_vehiculos.VehiculoRespuesta),
    ("OrdenCrear", contratos_ordenes.OrdenCrear),
    (
        "AsignacionMecanicoActualizar",
        contratos_ordenes.AsignacionMecanicoActualizar,
    ),
    (
        "CapacidadMecanicoActualizar",
        contratos_ordenes.CapacidadMecanicoActualizar,
    ),
    (
        "CapacidadMecanicoRespuesta",
        contratos_ordenes.CapacidadMecanicoRespuesta,
    ),
    (
        "CupoDiarioIngresosActualizar",
        contratos_ordenes.CupoDiarioIngresosActualizar,
    ),
    (
        "CupoDiarioIngresosRespuesta",
        contratos_ordenes.CupoDiarioIngresosRespuesta,
    ),
    ("OrdenRespuesta", contratos_ordenes.OrdenRespuesta),
    (
        "HistorialOrdenesVehiculoRespuesta",
        contratos_ordenes.HistorialOrdenesVehiculoRespuesta,
    ),
    ("CambioEstadoSolicitud", contratos_ordenes.CambioEstadoSolicitud),
    ("EntregaSolicitud", contratos_ordenes.EntregaSolicitud),
    ("EntregaOrdenRespuesta", contratos_ordenes.EntregaOrdenRespuesta),
    ("CancelacionClienteSolicitud", contratos_ordenes.CancelacionClienteSolicitud),
    ("SolicitudCancelacionRespuesta", contratos_ordenes.SolicitudCancelacionRespuesta),
    ("HistorialEstadoRespuesta", contratos_ordenes.HistorialEstadoRespuesta),
    ("RepuestoBitacoraEntrada", contratos_ordenes.RepuestoBitacoraEntrada),
    ("RepuestoBitacoraRespuesta", contratos_ordenes.RepuestoBitacoraRespuesta),
    ("BitacoraCrear", contratos_ordenes.BitacoraCrear),
    ("BitacoraRespuesta", contratos_ordenes.BitacoraRespuesta),
    ("EvidenciaSubida", contratos_evidencias.EvidenciaSubida),
    ("EvidenciaRespuesta", contratos_evidencias.EvidenciaRespuesta),
    ("UrlDescargaRespuesta", contratos_evidencias.UrlDescargaRespuesta),
    ("DecisionOrdenSolicitud", DecisionOrdenSolicitud),
    ("DecisionPresupuestoVerificada", DecisionPresupuestoVerificada),
    ("AplicacionDecisionRespuesta", AplicacionDecisionRespuesta),
    ("DecisionAplicacionPendiente", DecisionAplicacionPendiente),
    ("EnvioPresupuestoSolicitud", EnvioPresupuestoSolicitud),
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


_PARAMETRO_EVIDENCIA_ID: dict[str, object] = {
    "name": "evidencia_id",
    "in": "path",
    "required": True,
    "description": "Identificador (UUID) de la evidencia.",
    "schema": {
        "type": "string",
        "format": "uuid",
        "example": "3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f",
    },
}

_PARAMETRO_ORDEN_ID_QUERY: dict[str, object] = {
    "name": "orden_id",
    "in": "query",
    "required": True,
    "description": "Orden de trabajo (MS2) cuyas evidencias se listan.",
    "schema": {"type": "integer", "format": "int64", "minimum": 1, "example": 31},
}

_PARAMETROS_NOTIFICACIONES: list[dict[str, object]] = [
    {
        "name": "limite",
        "in": "query",
        "required": False,
        "description": "Cantidad máxima de notificaciones a devolver (1–100).",
        "schema": {"type": "integer", "default": 50, "minimum": 1, "maximum": 100},
    },
    {
        "name": "offset",
        "in": "query",
        "required": False,
        "description": "Cantidad de notificaciones que se omiten al paginar.",
        "schema": {"type": "integer", "default": 0, "minimum": 0},
    },
]


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
    parametros_extra: list[dict[str, object]] | None = None,
    cuerpo_multipart: str | None = None,
    cuerpo_requerido: bool = True,
    descripcion_404: str = (
        "Ruta no encontrada en la Gateway (RUTA_NO_ENCONTRADA)."
    ),
    esquema_404: dict[str, object] | None = None,
    descripcion_503: str | None = None,
) -> dict[str, object]:
    parametros: list[dict[str, object]] = [_PARAMETRO_X_REQUEST_ID]
    if con_vehiculo_id:
        parametros.append(_PARAMETRO_VEHICULO_ID)
    if con_orden_id:
        parametros.append(_PARAMETRO_ORDEN_ID)
    parametros.extend(parametros_extra or [])

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
        "502": {
            **_respuesta(
                "Microservicio no disponible (MICROSERVICIO_INALCANZABLE).",
                _ref("ErrorRespuesta"),
            ),
            "headers": {
                "Retry-After": {
                    "description": "Segundos sugeridos antes de reintentar un GET.",
                    "schema": {"type": "integer", "example": 5},
                }
            },
        },
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

    if descripcion_503 is not None:
        errores["503"] = _respuesta(
            descripcion_503 + "; o pool de la Gateway agotado.",
            {"oneOf": [_ref("ErrorDetalle"), _ref("ErrorRespuesta")]},
        )

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
            "required": cuerpo_requerido,
            "content": {"application/json": {"schema": _ref(cuerpo)}},
        }
    if cuerpo_multipart is not None:
        operacion["requestBody"] = {
            "required": True,
            "content": {"multipart/form-data": {"schema": _ref(cuerpo_multipart)}},
        }
    return operacion


def _operacion_evidencias(**kwargs: object) -> dict[str, object]:
    """Operación de MS4: además del 503 de la Gateway, MS4 responde 503 propio.

    MS4 devuelve `{"detail": ...}` con 503 cuando el almacenamiento (MinIO/S3)
    o MS2 (verificación de la orden) no responden; por eso el 503 de estas
    operaciones admite ambos formatos en lugar de la respuesta reutilizable.
    """
    operacion = _operacion(tag="Evidencias", requiere_auth=True, **kwargs)  # type: ignore[arg-type]
    operacion["responses"]["503"] = _respuesta(
        (
            "No disponible. MS4 responde {'detail': ...} si el almacenamiento, "
            "la base o el servicio de órdenes/presupuestos no responden (la "
            "subida se compensa, sin archivos ni filas a medias); la Gateway responde "
            "GATEWAY_SATURADA si su pool está agotado."
        ),
        {"oneOf": [_ref("ErrorRespuesta"), _ref("ErrorDetalle")]},
    )
    return operacion


def _caminos_evidencias() -> dict[str, dict[str, object]]:
    error_404_ms4: dict[str, object] = {
        "oneOf": [_ref("ErrorRespuesta"), _ref("ErrorDetalle")],
    }
    subir = _operacion_evidencias(
        resumen="Subir una evidencia de una orden",
        descripcion=(
            "Formulario multipart con el archivo y sus datos. Solo Mecánico "
            "(de una orden que atiende) o Administrador; un Cliente recibe 403 "
            "antes de procesar el archivo. MS4 verifica la orden contra MS2 con "
            "el mismo JWT antes de guardar nada. El autor sale del token y el "
            "`X-Request-ID` queda registrado con la evidencia. La orden no "
            "puede estar entregada ni cancelada (409) y un `presupuesto_id` "
            "debe pertenecer a la misma orden (MS3). Formatos aceptados: JPG, "
            "PNG, WEBP, MP4 y MOV, verificados por su contenido (415 para el "
            "resto o si los bytes no coinciden con el tipo declarado; 422 si "
            "el archivo está dañado). Fotos hasta 10 MiB (413 de MS4); la "
            "Gateway rechaza con 413 un body mayor a 12 MiB."
        ),
        operation_id="subir_evidencia",
        cuerpo=None,
        cuerpo_multipart="EvidenciaSubida",
        respuestas_ok={
            "201": _respuesta("Evidencia guardada.", _ref("EvidenciaRespuesta"))
        },
        errores_ms={
            "401": "JWT ausente o inválido",
            "403": "Se requiere rol Mecánico o Administrador",
            "400": "No se pudo leer el archivo enviado",
            "409": "La orden está entregada o cancelada",
            "415": (
                "Formato no permitido (solo JPG, PNG, WEBP, MP4 y MOV) o "
                "contenido distinto al tipo declarado"
            ),
            "422": (
                "Archivo vacío o dañado, presupuesto inexistente o de otra "
                "orden, o datos del formulario inválidos"
            ),
        },
        descripcion_404=(
            "Orden no encontrada: no existe o no es visible para el usuario "
            "(no se revela cuál de las dos)."
        ),
        esquema_404=error_404_ms4,
    )
    subir["responses"]["413"] = _respuesta(
        "El archivo es demasiado grande: la Gateway rechaza un body mayor a "
        "12 MiB (CUERPO_DEMASIADO_GRANDE) y MS4 una foto mayor a 10 MiB o un "
        "video mayor a su límite (`{\"detail\": ...}`).",
        {"oneOf": [_ref("ErrorRespuesta"), _ref("ErrorDetalle")]},
    )
    return {
        "/api/evidencias": {
            "post": subir,
            "get": _operacion_evidencias(
                resumen="Listar las evidencias de una orden",
                descripcion=(
                    "MS4 verifica primero que la orden sea visible para el "
                    "usuario (MS2). Cliente: solo las visibles para él, "
                    "confirmadas y no eliminadas. Mecánico: todas las no "
                    "eliminadas de las órdenes que atiende. Administrador: "
                    "todas, incluidas las eliminadas. En un usuario multirol "
                    "rige el alcance más amplio. Orden de creación ascendente."
                ),
                operation_id="listar_evidencias",
                cuerpo=None,
                parametros_extra=[_PARAMETRO_ORDEN_ID_QUERY],
                respuestas_ok={
                    "200": _respuesta(
                        "Evidencias de la orden.",
                        {"type": "array", "items": _ref("EvidenciaRespuesta")},
                    )
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "422": "Falta orden_id o no es un entero positivo",
                },
                descripcion_404="Orden no encontrada o no visible.",
                esquema_404=error_404_ms4,
            ),
        },
        "/api/evidencias/{evidencia_id}": {
            "get": _operacion_evidencias(
                resumen="Consultar una evidencia",
                descripcion=(
                    "Aplica la misma visibilidad del listado. Una evidencia "
                    "inexistente, eliminada o fuera del alcance responde el "
                    "mismo 404, sin revelar su existencia."
                ),
                operation_id="consultar_evidencia",
                cuerpo=None,
                parametros_extra=[_PARAMETRO_EVIDENCIA_ID],
                respuestas_ok={
                    "200": _respuesta("Evidencia encontrada.", _ref("EvidenciaRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "422": "Identificador de evidencia inválido (no es UUID)",
                },
                descripcion_404="Evidencia no encontrada.",
                esquema_404=error_404_ms4,
            )
        },
        "/api/evidencias/{evidencia_id}/descarga": {
            "get": _operacion_evidencias(
                resumen="Obtener la URL de descarga de una evidencia",
                descripcion=(
                    "Devuelve una URL prefirmada del almacenamiento que vence "
                    "en `expira_en` segundos (5 minutos por defecto) y fuerza "
                    "el tipo validado y la descarga como adjunto. El cliente la "
                    "abre directamente (no pasa por la Gateway) y pide una "
                    "nueva cuando vence. La respuesta lleva `Cache-Control: "
                    "no-store` y `X-Content-Type-Options: nosniff`. Mismo 404 "
                    "que el detalle."
                ),
                operation_id="descargar_evidencia",
                cuerpo=None,
                parametros_extra=[_PARAMETRO_EVIDENCIA_ID],
                respuestas_ok={
                    "200": {
                        **_respuesta(
                            "URL prefirmada de corta duración.",
                            _ref("UrlDescargaRespuesta"),
                        ),
                        "headers": {
                            "Cache-Control": {
                                "description": "La URL no se debe cachear.",
                                "schema": {"type": "string", "example": "no-store"},
                            },
                            "X-Content-Type-Options": {
                                "description": "El navegador no adivina el tipo.",
                                "schema": {"type": "string", "example": "nosniff"},
                            },
                        },
                    }
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "422": "Identificador de evidencia inválido (no es UUID)",
                },
                descripcion_404="Evidencia no encontrada.",
                esquema_404=error_404_ms4,
            )
        },
    }


def _caminos_documentados() -> dict[str, dict[str, object]]:
    # Un recurso ausente lo informa MS2 con {"detail": ...}; la Gateway
    # conserva además su formato propio para errores que ella genera.
    error_404_recurso: dict[str, object] = {
        "oneOf": [_ref("ErrorRespuesta"), _ref("ErrorDetalle")],
    }

    caminos = {
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
                errores_ms={
                    "401": "Credenciales inválidas",
                    "403": (
                        "Credenciales correctas, pero la cuenta no tiene roles: "
                        "no puede emitirse un token"
                    ),
                    "422": "Body inválido (correo con formato inválido o campos ausentes)",
                    "429": (
                        "Demasiados intentos fallidos: la cuenta queda bloqueada "
                        "temporalmente. `Retry-After` indica los segundos restantes"
                    ),
                },
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
        "/api/notificaciones": {
            "get": _operacion(
                tag="Notificaciones",
                resumen="Consultar mis notificaciones",
                descripcion=(
                    "Devuelve la bandeja del usuario autenticado, ordenada de "
                    "más reciente a más antigua. Cada usuario solo puede ver "
                    "sus propias notificaciones."
                ),
                operation_id="consultar_notificaciones",
                cuerpo=None,
                parametros_extra=_PARAMETROS_NOTIFICACIONES,
                respuestas_ok={
                    "200": _respuesta(
                        "Notificaciones del usuario.",
                        {"type": "array", "items": _ref("NotificacionRespuesta")},
                    ) | {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": _ref("NotificacionRespuesta"),
                                },
                                "examples": {
                                    "bandeja_vacia": {
                                        "summary": "Sin notificaciones",
                                        "description": "La bandeja aún no contiene avisos.",
                                        "value": [],
                                    }
                                },
                            }
                        }
                    }
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "422": "Parámetros de paginación inválidos",
                },
                requiere_auth=True,
            )
        },
        "/api/inventario/ordenes/{orden_id}/disponibilidad": {
            "post": _operacion(
                tag="Inventario",
                resumen="Confirmar disponibilidad y reservar repuestos",
                descripcion=(
                    "Solo Administrador. MS3 reserva las unidades enteras del "
                    "alcance aprobado si el stock libre las cubre, descontando "
                    "compromisos de otras órdenes. Luego coordina con MS2 el "
                    "cambio auditado a En reparación. Una respuesta 503 indica "
                    "que la reserva quedó persistida y se debe repetir la misma "
                    "operación para confirmar su aplicación."
                ),
                operation_id="confirmar_disponibilidad_repuestos",
                cuerpo=None,
                con_orden_id=True,
                respuestas_ok={
                    "200": _respuesta(
                        "Reserva confirmada y transición aplicada.",
                        _ref("DisponibilidadRepuestosRespuesta"),
                    ) | {
                        "content": {
                            "application/json": {
                                "schema": _ref("DisponibilidadRepuestosRespuesta"),
                                "examples": {
                                    "reserva_confirmada": {
                                        "summary": "Reserva confirmada",
                                        "description": (
                                            "El presupuesto aprobado quedó reservado "
                                            "y la orden inició su reparación."
                                        ),
                                        "value": {
                                            "clave_operacion": "disp:31:4",
                                            "orden_id": 31,
                                            "version_presupuesto": 4,
                                            "repuestos": [
                                                {"repuesto_id": 8, "cantidad": 2}
                                            ],
                                            "aplicacion_confirmada": True,
                                        },
                                    }
                                },
                            }
                        }
                    }
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador",
                    "409": "Stock libre insuficiente o estado incompatible",
                    "422": "Cantidad de repuesto fraccionaria",
                    "503": "MS2 no confirmó la transición; reintentar con la misma clave",
                },
                requiere_auth=True,
                descripcion_404="Orden o presupuesto inexistente.",
                esquema_404={
                    "oneOf": [_ref("ErrorRespuesta"), _ref("ErrorDetalle")]
                },
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
                descripcion=(
                    "Administrador lista todos los vehículos del taller; "
                    "Cliente lista los suyos. Un Mecánico recibe 403 y usa "
                    "/api/vehiculos/asignados."
                ),
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
                    "403": "Se requiere rol Cliente o Administrador",
                },
                requiere_auth=True,
                descripcion_404="No existe el perfil Cliente local en MS2.",
                esquema_404=error_404_recurso,
            ),
        },
        "/api/vehiculos/asignados": {
            "get": _operacion(
                tag="Vehículos",
                resumen="Listar vehículos asignados al mecánico",
                descripcion=(
                    "Solo un Mecánico lista los vehículos con órdenes de "
                    "trabajo que tiene asignadas."
                ),
                operation_id="listar_vehiculos_asignados",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta(
                        "Lista de vehículos asignados (sin duplicados).",
                        {"type": "array", "items": _ref("VehiculoRespuesta")},
                    )
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Mecánico",
                },
                requiere_auth=True,
            ),
        },
        "/api/vehiculos/{vehiculo_id}": {
            "get": _operacion(
                tag="Vehículos",
                resumen="Consultar un vehículo",
                descripcion=(
                    "Devuelve un vehículo según el rol: Cliente solo el propio, "
                    "Administrador cualquiera del taller y Mecánico solo los "
                    "que tiene asignados."
                ),
                operation_id="consultar_vehiculo",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta("Vehículo encontrado.", _ref("VehiculoRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "422": "Identificador de vehículo inválido",
                },
                requiere_auth=True,
                con_vehiculo_id=True,
                descripcion_404=(
                    "No encontrado. Si el vehículo no existe o no está entre "
                    "los accesibles por el rol, el microservicio responde "
                    "{'detail': 'Vehículo no encontrado'}."
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
                    "registrado. Si no hay un ingreso abierto, valida el cupo "
                    "diario antes de crearlo; reutilizar un ingreso abierto no "
                    "consume otro cupo. La orden comienza en Recibido y puede "
                    "quedar sin mecánico."
                ),
                operation_id="crear_orden",
                cuerpo="OrdenCrear",
                respuestas_ok={
                    "201": _respuesta("Orden creada.", _ref("OrdenRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador",
                    "409": "Cupo diario agotado o aún no configurado",
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
                    "rechazan la operación. MS2 consulta MS1 con el JWT del "
                    "Administrador: el destino debe existir, estar activo y "
                    "tener rol Mecánico (422 en otro caso). Si MS1 no permite "
                    "validarlo, responde 503 sin guardar cambios."
                ),
                operation_id="asignar_mecanico",
                cuerpo="AsignacionMecanicoActualizar",
                respuestas_ok={
                    "200": _respuesta("Responsable actualizado.", _ref("OrdenRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador",
                    "409": "Autoasignación, estado terminal o capacidad excedida/no configurada",
                    "422": "Destino inexistente, inactivo, sin rol Mecánico o datos inválidos",
                },
                requiere_auth=True,
                con_orden_id=True,
                descripcion_404="Orden no encontrada.",
                esquema_404=error_404_recurso,
                descripcion_503="No fue posible validar el mecánico con MS1",
            )
        },
        "/api/ordenes/configuracion/capacidad/mecanicos": {
            "get": _operacion(
                tag="Órdenes",
                resumen="Consultar la capacidad máxima por mecánico",
                descripcion=(
                    "Solo Administrador. Devuelve el máximo configurado y, si "
                    "se redujo por debajo del uso actual, informa los mecánicos "
                    "que superan el nuevo límite. Un valor nulo indica que aún "
                    "no se ha configurado capacidad."
                ),
                operation_id="consultar_capacidad_mecanicos",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta(
                        "Configuración de capacidad.",
                        _ref("CapacidadMecanicoRespuesta"),
                    )
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador",
                },
                requiere_auth=True,
            ),
            "put": _operacion(
                tag="Órdenes",
                resumen="Configurar el máximo de órdenes activas por mecánico",
                descripcion=(
                    "Solo Administrador. El valor debe ser un entero positivo. "
                    "Cada cambio guarda el valor anterior y el nuevo, el actor "
                    "y la fecha. Si hay mecánicos sobre el nuevo límite, se "
                    "informan sin cancelar ni desasignar órdenes existentes."
                ),
                operation_id="actualizar_capacidad_mecanicos",
                cuerpo="CapacidadMecanicoActualizar",
                respuestas_ok={
                    "200": _respuesta(
                        "Configuración actualizada.",
                        _ref("CapacidadMecanicoRespuesta"),
                    )
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador",
                    "422": "El máximo debe ser un entero positivo",
                },
                requiere_auth=True,
            ),
        },
        "/api/ordenes/configuracion/capacidad/ingresos-diarios": {
            "get": _operacion(
                tag="Órdenes",
                resumen="Consultar el cupo diario de ingresos físicos",
                descripcion=(
                    "Solo Administrador. Devuelve el límite y el número de "
                    "ingresos físicos de la jornada local actual. Cuenta nuevas "
                    "estancias, no órdenes que reutilizan un ingreso abierto."
                ),
                operation_id="consultar_cupo_diario_ingresos",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta(
                        "Cupo diario y uso de la jornada.",
                        _ref("CupoDiarioIngresosRespuesta"),
                    )
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador",
                },
                requiere_auth=True,
            ),
            "put": _operacion(
                tag="Órdenes",
                resumen="Configurar el máximo diario de ingresos físicos",
                descripcion=(
                    "Solo Administrador. El máximo debe ser un entero positivo. "
                    "Se auditan valor anterior, nuevo, administrador y fecha. "
                    "Si la jornada ya supera el límite reducido, se informa sin "
                    "eliminar ingresos; se bloquean nuevos ingresos físicos."
                ),
                operation_id="actualizar_cupo_diario_ingresos",
                cuerpo="CupoDiarioIngresosActualizar",
                respuestas_ok={
                    "200": _respuesta(
                        "Cupo diario actualizado.",
                        _ref("CupoDiarioIngresosRespuesta"),
                    )
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador",
                    "422": "El máximo debe ser un entero positivo",
                },
                requiere_auth=True,
            ),
        },
        "/api/ordenes/vehiculo/{vehiculo_id}/historial": {
            "get": _operacion(
                tag="Órdenes",
                resumen="Consultar historial paginado de órdenes por vehículo",
                descripcion=(
                    "Filtro en MS2 por vehículo y página ordenada por creación "
                    "descendente, con ID descendente como desempate. Administrador "
                    "ve todas; Cliente solo un vehículo propio; Mecánico solo sus "
                    "órdenes actualmente asignadas. Un vehículo visible sin órdenes "
                    "devuelve items vacío y total 0."
                ),
                operation_id="consultar_historial_ordenes_vehiculo",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta(
                        "Página del historial del vehículo.",
                        _ref("HistorialOrdenesVehiculoRespuesta"),
                    )
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "422": "Identificador o parámetros de página inválidos",
                    "404": "Vehículo inexistente o fuera de visibilidad",
                    "500": "No fue posible consultar el historial",
                },
                requiere_auth=True,
                con_vehiculo_id=True,
                parametros_extra=[
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "description": (
                            "Cantidad de elementos: 20 por defecto, entre 1 y 100."
                        ),
                        "schema": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20,
                        },
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "required": False,
                        "description": "Índice inicial, desde cero.",
                        "schema": {
                            "type": "integer",
                            "minimum": 0,
                            "default": 0,
                        },
                    },
                ],
                descripcion_404="Vehículo inexistente o no visible.",
                esquema_404=error_404_recurso,
            )
        },
        "/api/ordenes/{orden_id}/historial": {
            "get": _operacion(
                tag="Órdenes",
                resumen="Consultar el historial de estados de una orden",
                descripcion=(
                    "Devuelve todos los registros por fecha/hora e identificador "
                    "ascendente, con el actor, origen y observación. Aplica la "
                    "misma visibilidad del detalle: Administrador ve todas; "
                    "Cliente sus vehículos; Mecánico sus órdenes asignadas; "
                    "multirol combina los alcances. Una orden inexistente o "
                    "ajena responde 404; una visible sin registros devuelve []."
                ),
                operation_id="consultar_historial_orden",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta(
                        "Historial de estados.",
                        {
                            "type": "array",
                            "items": _ref("HistorialEstadoRespuesta"),
                        },
                    )
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
        "/api/ordenes/{orden_id}/bitacora": {
            "get": _operacion(
                tag="Órdenes",
                resumen="Consultar la bitácora de trabajo de una orden",
                descripcion=(
                    "Devuelve todos los registros por fecha/hora e identificador "
                    "ascendente, con el autor, el tipo (observación o acción), el "
                    "texto y los repuestos utilizados. Aplica la misma visibilidad "
                    "del detalle: Administrador ve todas; Cliente sus vehículos; "
                    "Mecánico sus órdenes asignadas; multirol combina los alcances. "
                    "Una orden inexistente o ajena responde 404; una visible sin "
                    "registros devuelve []."
                ),
                operation_id="consultar_bitacora_orden",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta(
                        "Bitácora de trabajo de la orden.",
                        {"type": "array", "items": _ref("BitacoraRespuesta")},
                    )
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "422": "Identificador de orden inválido",
                },
                requiere_auth=True,
                con_orden_id=True,
                descripcion_404="Orden inexistente o no visible.",
                esquema_404=error_404_recurso,
            ),
            "post": _operacion(
                tag="Órdenes",
                resumen="Registrar una observación o acción en la bitácora",
                descripcion=(
                    "Registra lo que el mecánico observa o ejecuta sobre una orden "
                    "sin cambiar su estado. Una observación es una nota libre; una "
                    "acción puede declarar los repuestos utilizados (texto libre y "
                    "cantidad). Solo el mecánico asignado o un administrador pueden "
                    "registrarla. No acepta estado, actor ni fecha en el cuerpo."
                ),
                operation_id="registrar_bitacora_orden",
                cuerpo="BitacoraCrear",
                respuestas_ok={
                    "201": _respuesta(
                        "Entrada registrada.", _ref("BitacoraRespuesta")
                    )
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere ser el mecánico asignado o Administrador",
                    "422": "Tipo, descripción o repuestos inválidos",
                },
                requiere_auth=True,
                con_orden_id=True,
                descripcion_404="Orden no encontrada o ajena.",
                esquema_404=error_404_recurso,
            ),
        },
        "/api/ordenes/{orden_id}/estado": {
            "patch": _operacion(
                tag="Órdenes",
                resumen="Cambiar el estado de una orden",
                descripcion=(
                    "Cambia el estado validando rol, catálogo oficial y "
                    "transición declarada por el dominio. La primera asignación (1 → 2) "
                    "requiere PUT /api/ordenes/{orden_id}/mecanico; el envío inicial "
                    "(2 → 3) requiere POST /api/presupuestos/{presupuesto_id}/versiones/"
                    "{numero}/envio, que coordina la aplicación con MS2; la primera "
                    "decisión (3 → 4/5/8) requiere POST /api/ordenes/{orden_id}/"
                    "decisiones-presupuesto con una decisión verificada de MS3. El PATCH "
                    "directo responde 409 para esos pares, también para usuarios "
                    "multirrol. Bloquea además 4 → 5 hasta verificar disponibilidad, "
                    "6 → 7 hasta registrar la entrega y cualquier destino Cancelado "
                    "genérico; bloquearlos no implementa esos flujos. Solo permite "
                    "5 → 6 al Mecánico asignado; devuelve 403 a otros actores. Esa "
                    "operación todavía no acredita que el trabajo autorizado haya "
                    "terminado. Entregado y Cancelado son terminales. Pasar a Cancelado "
                    "exige un motivo no vacío; en otros destinos es opcional. Los "
                    "rechazos no modifican estado ni historial y el cambio permitido "
                    "guarda ambos en la misma transacción local."
                ),
                operation_id="cambiar_estado_orden",
                cuerpo="CambioEstadoSolicitud",
                respuestas_ok={
                    "200": _respuesta("Orden con su nuevo estado.", _ref("OrdenRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador o ser el mecánico asignado",
                    "409": "Transición no permitida, terminal o reservada a una operación específica",
                    "422": "Estado de destino desconocido, cancelación sin motivo o datos inválidos",
                },
                requiere_auth=True,
                con_orden_id=True,
                descripcion_404="Orden no encontrada.",
                esquema_404=error_404_recurso,
            )
        },
        "/api/ordenes/{orden_id}/entrega": {
            "post": _operacion(
                tag="Órdenes",
                resumen="Registrar la entrega física de una orden lista",
                descripcion=(
                    "Cierra el ciclo normal (6 → 7): registra la fecha de entrega "
                    "y la identidad que la autorizó. Solo el Administrador puede "
                    "invocarla y reemplaza al PATCH directo 6 → 7, que responde 409. "
                    "Repetir una entrega válida devuelve el registro original sin "
                    "duplicar historial. Otro estado responde 409; una entrega "
                    "histórica sin auditoría completa responde 500."
                ),
                operation_id="registrar_entrega_orden",
                cuerpo="EntregaSolicitud",
                cuerpo_requerido=False,
                respuestas_ok={
                    "200": _respuesta("Orden entregada; un reintento conserva la entrega original.", _ref("EntregaOrdenRespuesta"))
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Administrador",
                    "409": "La orden no está Lista o ya es terminal",
                    "422": "Observación de entrega vacía",
                },
                requiere_auth=True,
                con_orden_id=True,
                descripcion_404="Orden no encontrada.",
                esquema_404=error_404_recurso,
            )
        },
        "/api/ordenes/{orden_id}/cancelacion": {
            "post": _operacion(
                tag="Órdenes",
                resumen="Solicitar la cancelación administrativa de una orden",
                descripcion=(
                    "El Cliente propietario registra un motivo auditable sin cambiar "
                    "el estado. Un Administrador debe revisar y confirmar por la "
                    "operación específica. MS2 verifica en MS3 que no exista una "
                    "aprobación inicial. Repetir el mismo motivo devuelve la solicitud "
                    "pendiente existente."
                ),
                operation_id="solicitar_cancelacion_orden",
                cuerpo="CancelacionClienteSolicitud",
                respuestas_ok={
                    "201": _respuesta("Solicitud pendiente de revisión.", _ref("SolicitudCancelacionRespuesta")),
                    "200": _respuesta("Solicitud pendiente existente.", _ref("SolicitudCancelacionRespuesta")),
                },
                errores_ms={
                    "401": "JWT ausente o inválido",
                    "403": "Se requiere rol Cliente",
                    "409": "Orden no cancelable, solicitud existente o aprobación inicial registrada",
                    "422": "Motivo de cancelación vacío o datos inválidos",
                    "503": "No fue posible verificar MS3",
                },
                requiere_auth=True,
                con_orden_id=True,
                descripcion_404="Orden no encontrada o ajena.",
                esquema_404=error_404_recurso,
            )
        },
        "/api/ordenes/cancelaciones/pendientes": {
            "get": _operacion(
                tag="Órdenes",
                resumen="Listar solicitudes pendientes de cancelación",
                descripcion="Solo Administrador. Devuelve los datos necesarios para revisar la solicitud.",
                operation_id="listar_cancelaciones_pendientes",
                cuerpo=None,
                respuestas_ok={"200": _respuesta(
                    "Solicitudes pendientes.",
                    {"type": "array", "items": _ref("SolicitudCancelacionRespuesta")},
                )},
                errores_ms={"401": "JWT ausente o inválido", "403": "Se requiere rol Administrador"},
                requiere_auth=True,
            )
        },
        "/api/ordenes/{orden_id}/cancelacion/confirmacion": {
            "post": _operacion(
                tag="Órdenes",
                resumen="Confirmar administrativamente una cancelación",
                descripcion=(
                    "Solo Administrador. Vuelve a comprobar en MS3 que no exista "
                    "aprobación inicial y registra el estado Cancelado con el "
                    "Administrador confirmante e historial en una transacción."
                ),
                operation_id="confirmar_cancelacion_orden",
                cuerpo=None,
                respuestas_ok={"200": _respuesta("Orden cancelada.", _ref("OrdenRespuesta"))},
                errores_ms={
                    "401": "JWT ausente o inválido", "403": "Se requiere rol Administrador",
                    "409": "No hay solicitud pendiente o existe una aprobación inicial",
                    "503": "No fue posible verificar MS3",
                },
                requiere_auth=True,
                con_orden_id=True,
                descripcion_404="Orden no encontrada.",
                esquema_404=error_404_recurso,
            )
        },
    }
    caminos["/api/ordenes/{orden_id}"]["get"]["parameters"].append({
        "name": "solo_propietario", "in": "query", "required": False,
        "schema": {"type": "boolean", "default": False},
        "description": "Exige propiedad como Cliente aunque el JWT incluya otros roles.",
    })
    caminos["/api/ordenes/{orden_id}"]["get"]["responses"]["200"]["headers"] = {
        "X-Orden-Propiedad-Verificada": {
            "description": "Solo con solo_propietario=true y propiedad confirmada por MS2.",
            "schema": {"type": "string", "enum": ["true"]},
        },
    }
    caminos.update(_caminos_decisiones(error_404_recurso))
    caminos.update(_caminos_usuarios())
    caminos["/api/ordenes/{orden_id}/envios-presupuesto"] = {
        "post": _operacion_envio_presupuesto(error_404_recurso)
    }
    return caminos


_PARAMETRO_USUARIO_ID: dict[str, object] = {
    "name": "usuario_id",
    "in": "path",
    "required": True,
    "description": "Identificador del usuario (MS1).",
    "schema": {"type": "integer", "example": 7},
}

_PARAMETRO_ROL: dict[str, object] = {
    "name": "rol",
    "in": "path",
    "required": True,
    "description": "Rol a retirar.",
    "schema": {
        "type": "string",
        "enum": ["cliente", "mecanico", "administrador"],
        "example": "mecanico",
    },
}

_EJEMPLO_USUARIO_MECANICO: dict[str, object] = {
    "id": 7,
    "email": "ana@correo.cl",
    "full_name": "Ana Pérez",
    "roles": ["cliente", "mecanico"],
    "is_active": True,
}

_ERROR_404_USUARIO: dict[str, object] = {
    "oneOf": [_ref("ErrorRespuesta"), _ref("ErrorDetalle")],
}


def _operacion_usuarios(*, ejemplo: object, **kwargs: object) -> dict[str, object]:
    """Operación de administración de usuarios (MS1) con su ejemplo de éxito."""
    operacion = _operacion(tag="Usuarios", requiere_auth=True, **kwargs)  # type: ignore[arg-type]
    operacion["responses"]["200"]["content"]["application/json"]["examples"] = {
        "ejemplo": {"value": ejemplo}
    }
    return operacion


def _caminos_usuarios() -> dict[str, dict[str, object]]:
    """Administración de usuarios y roles de MS1 (solo Administrador)."""
    errores_admin = {
        "401": "JWT ausente o inválido",
        "403": "Se requiere rol Administrador",
    }
    asignar = _operacion_usuarios(
        resumen="Asignar un rol restringido a un usuario",
        descripcion=(
            "Solo Administrador. Asigna un rol a una cuenta existente; un rol "
            "desconocido responde 422. La asignación queda registrada con el "
            "administrador que la hizo."
        ),
        operation_id="asignar_rol_usuario",
        cuerpo="RolAsignarSolicitud",
        parametros_extra=[_PARAMETRO_USUARIO_ID],
        respuestas_ok={
            "200": _respuesta("Usuario con el rol asignado.", _ref("UsuarioRespuesta"))
        },
        errores_ms={**errores_admin, "422": "Rol desconocido o body inválido"},
        descripcion_404="El usuario no existe.",
        esquema_404=_ERROR_404_USUARIO,
        ejemplo=_EJEMPLO_USUARIO_MECANICO,
    )
    asignar["requestBody"]["content"]["application/json"]["examples"] = {
        "mecanico": {"value": {"rol": "mecanico"}}
    }
    return {
        "/api/auth/usuarios": {
            "get": _operacion_usuarios(
                resumen="Listar todos los usuarios",
                descripcion=(
                    "Solo Administrador. Una cuenta sin roles se lista con `roles: []`."
                ),
                operation_id="listar_usuarios",
                cuerpo=None,
                respuestas_ok={
                    "200": _respuesta(
                        "Usuarios registrados.",
                        {"type": "array", "items": _ref("UsuarioRespuesta")},
                    )
                },
                errores_ms=errores_admin,
                ejemplo=[_EJEMPLO_USUARIO_MECANICO],
            )
        },
        "/api/auth/usuarios/{usuario_id}": {
            "get": _operacion_usuarios(
                resumen="Consultar un usuario por su identificador",
                descripcion="Solo Administrador.",
                operation_id="consultar_usuario",
                cuerpo=None,
                parametros_extra=[_PARAMETRO_USUARIO_ID],
                respuestas_ok={
                    "200": _respuesta("Usuario encontrado.", _ref("UsuarioRespuesta"))
                },
                errores_ms={**errores_admin, "422": "Identificador inválido"},
                descripcion_404="El usuario no existe.",
                esquema_404=_ERROR_404_USUARIO,
                ejemplo=_EJEMPLO_USUARIO_MECANICO,
            )
        },
        "/api/auth/usuarios/{usuario_id}/roles": {"post": asignar},
        "/api/auth/usuarios/{usuario_id}/roles/{rol}": {
            "delete": _operacion_usuarios(
                resumen="Retirar un rol restringido a un usuario",
                descripcion=(
                    "Solo Administrador. Si era el último rol, la cuenta queda con "
                    "`roles: []` y la respuesta no falla."
                ),
                operation_id="retirar_rol_usuario",
                cuerpo=None,
                parametros_extra=[_PARAMETRO_USUARIO_ID, _PARAMETRO_ROL],
                respuestas_ok={
                    "200": _respuesta(
                        "Usuario sin el rol retirado.", _ref("UsuarioRespuesta")
                    )
                },
                errores_ms={
                    **errores_admin,
                    "422": "Rol desconocido o identificador inválido",
                },
                descripcion_404="El usuario no existe.",
                esquema_404=_ERROR_404_USUARIO,
                ejemplo={**_EJEMPLO_USUARIO_MECANICO, "roles": ["cliente"]},
            )
        },
    }


def _operacion_envio_presupuesto(error_404: dict[str, object]) -> dict[str, object]:
    """Coordinación MS3 -> MS2 del primer envío de presupuesto (orden 2 -> 3)."""
    operacion = _operacion(
        tag="Órdenes",
        resumen="Aplicar el envío inicial de presupuesto verificado en MS3",
        descripcion=(
            "Solo Administrador; lo invoca MS3 al enviar la primera versión. Recibe "
            "solo `presupuesto_id`, verifica el envío en MS3 con el JWT original y "
            "deriva la transición 2 -> 3; no acepta actor ni estado destino. Es "
            "idempotente: repetir la referencia devuelve la aplicación registrada."
        ),
        operation_id="aplicar_envio_presupuesto",
        cuerpo="EnvioPresupuestoSolicitud",
        respuestas_ok={
            "200": _respuesta(
                "Transición aplicada (o ya aplicada).",
                _ref("AplicacionEnvioPresupuestoRespuesta"),
            )
        },
        errores_ms={
            "401": "JWT ausente o inválido",
            "403": "Se requiere rol Administrador",
            "409": "Estado incompatible con el envío inicial",
            "422": "Datos inválidos",
        },
        requiere_auth=True,
        con_orden_id=True,
        descripcion_404="Orden o envío inicial no encontrado.",
        esquema_404=error_404,
    )
    operacion["requestBody"]["content"]["application/json"]["examples"] = {
        "referencia": {"value": {"presupuesto_id": 7}}
    }
    operacion["responses"]["200"]["content"]["application/json"]["examples"] = {
        "ejemplo": {
            "value": {
                "presupuesto_id": 7,
                "orden_id": 31,
                "estado_aplicado": 3,
                "historial_id": 40,
            }
        }
    }
    operacion["responses"]["503"] = _respuesta(
        "No fue posible verificar el envío en MS3; o pool de la Gateway agotado.",
        {"oneOf": [_ref("ErrorDetalle"), _ref("ErrorRespuesta")]},
    )
    return operacion


def _caminos_decisiones(error_404: dict[str, object]) -> dict[str, dict[str, object]]:
    aplicada = {"decision_id": 9, "orden_id": 31, "estado_aplicado": 8, "historial_id": 40}
    hecho = {"decision_id": 9, "orden_id": 31, "cliente_usuario_id": 42,
             "decision": "rechazado", "primera_decision": True,
             "repuestos_disponibles": None, "motivo": "No autorizo el servicio"}
    parametros_decision = {"name": "decision_id", "in": "path", "required": True,
                           "schema": {"type": "integer", "exclusiveMinimum": 0}}
    operaciones = {}
    for ruta, metodo, tag, resumen, descripcion, contrato, cuerpo, errores in (
        ("/api/ordenes/{orden_id}/decisiones-presupuesto", "post", "Órdenes",
         "Aplicar una decisión de presupuesto",
         "Cliente propietario. Verifica el hecho en MS3 con el JWT original, deriva el evento "
         "y guarda estado e historial atómicamente. Repetir decision_id devuelve la aplicación "
         "registrada sin nuevas escrituras. No acepta actor, stock ni destino en el body.",
         "AplicacionDecisionRespuesta", "DecisionOrdenSolicitud",
         {"409": "Estado/evento incompatible o decisión no aplicable", "503": "MS3 no verificable"}),
        ("/api/presupuestos/decisiones/{decision_id}", "get", "Presupuestos",
         "Consultar una decisión persistida",
         "Solo el cliente que decidió. Devuelve el hecho y la disponibilidad guardada al aprobar; "
         "no recalcula stock ni consulta MS2. Una aprobación histórica sin evaluación responde 409.",
         "DecisionPresupuestoVerificada", None, {"409": "Decisión histórica sin evaluación de stock"}),
        ("/api/presupuestos/decisiones/{decision_id}/aplicacion", "post", "Presupuestos",
         "Reintentar la aplicación de una decisión",
         "Solo el cliente responsable. Reutiliza la decisión existente y su JWT, sin crear "
         "otra decisión. Un 503 identifica la decisión registrada cuya aplicación no se confirmó.",
         "AplicacionDecisionRespuesta", None,
         {"409": "No es una decisión inicial aplicable", "503": "Aplicación no confirmada en MS2"}),
    ):
        operacion = _operacion(
            tag=tag, resumen=resumen, descripcion=descripcion,
            operation_id={
                "/api/ordenes/{orden_id}/decisiones-presupuesto": "aplicar_decision_presupuesto",
                "/api/presupuestos/decisiones/{decision_id}": "consultar_decision_presupuesto",
                "/api/presupuestos/decisiones/{decision_id}/aplicacion": "reintentar_aplicacion_decision",
            }[ruta],
            cuerpo=cuerpo, respuestas_ok={"200": _respuesta(resumen, _ref(contrato))},
            errores_ms={"401": "JWT ausente o inválido", "403": "Se requiere rol Cliente",
                        "422": "Datos inválidos", **errores},
            requiere_auth=True, con_orden_id=ruta.startswith("/api/ordenes"),
            descripcion_404="Orden o decisión inexistente o ajena", esquema_404=error_404,
        )
        if "{decision_id}" in ruta:
            operacion["parameters"].append(parametros_decision)
        media = operacion["responses"]["200"]["content"]["application/json"]
        media["examples"] = {"ejemplo": {"value": hecho if metodo == "get" else aplicada}}
        if cuerpo:
            operacion["requestBody"]["content"]["application/json"]["examples"] = {
                "referencia": {"value": {"decision_id": 9}},
            }
        if "503" in errores:
            esquema_503 = "DecisionAplicacionPendiente" if ruta.startswith("/api/presupuestos") else "ErrorDetalle"
            operacion["responses"]["503"] = _respuesta(
                errores["503"] + "; o pool de Gateway agotado",
                {"oneOf": [_ref(esquema_503), _ref("ErrorRespuesta")]},
            )
        operaciones[ruta] = {metodo: operacion}
    return operaciones


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


def _exigir_campos_siempre_serializados(
    esquemas: dict[str, dict[str, object]], modelos: list[type[BaseModel]]
) -> None:
    """Marca obligatorios los campos con valor por defecto de las respuestas.

    Los esquemas se generan en modo validación, donde un campo con valor por
    defecto es opcional. En una respuesta, en cambio, FastAPI serializa siempre
    todos los campos: el cliente los recibe siempre. Los modelos de respuesta
    que lo declaran con `json_schema_serialization_defaults_required=True` (igual
    que su original en el microservicio) publican esos campos como obligatorios.
    Diferencia D-02 de `docs/diferencias-contrato-consumo-real.md`.
    """
    for modelo in modelos:
        if not modelo.model_config.get("json_schema_serialization_defaults_required"):
            continue
        definicion = esquemas.get(modelo.__name__)
        if definicion is None:
            raise ValueError(f"El modelo '{modelo.__name__}' no está en components.schemas")
        obligatorios = list(definicion.get("required", []))
        for nombre, campo in modelo.model_fields.items():
            clave = campo.alias or nombre
            if clave not in obligatorios:
                obligatorios.append(clave)
        definicion["required"] = obligatorios


def _documentar_bloqueo_login(esquema: dict[str, object]) -> None:
    """El `429` de login trae `Retry-After` con los segundos de bloqueo (MS1)."""
    respuesta = esquema["paths"]["/api/auth/login"]["post"]["responses"]["429"]
    respuesta["headers"] = {
        "Retry-After": {
            "description": "Segundos que faltan para que expire el bloqueo.",
            "schema": {"type": "integer", "example": 900},
        }
    }


def construir_openapi(app: FastAPI) -> dict[str, object]:
    """Arma el esquema OpenAPI de la Gateway con los contratos documentados.

    Parte del esquema autogenerado por FastAPI (índice y healthcheck) y le
    agrega los endpoints de negocio de los cuatro microservicios, la
    seguridad `bearerAuth` y los esquemas de `gateway/contratos` y
    `gateway/esquemas`.
    """
    # Import diferido: `openapi_ms3` reutiliza los ayudantes de este módulo.
    from gateway.openapi_ms3 import CONTRATOS_MS3, caminos_ms3, esquemas_ms3

    if getattr(app, "openapi_schema", None) is not None:
        return app.openapi_schema

    esquema = get_openapi(
        title=_TITULO,
        version=_VERSION,
        description=_DESCRIPCION,
        routes=app.routes,
        tags=_TAGS,
    )
    # Una misma ruta puede publicar métodos de módulos distintos (p. ej.
    # GET de disponibilidad y POST de reserva). Conservar ambos métodos.
    for caminos in (_caminos_documentados(), _caminos_evidencias(), caminos_ms3()):
        for ruta, operaciones in caminos.items():
            esquema["paths"].setdefault(ruta, {}).update(operaciones)

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
    for nombre, definicion in esquemas_ms3().items():
        existente = componentes["schemas"].setdefault(nombre, definicion)
        if existente.get("properties") != definicion.get("properties"):
            raise ValueError(f"Esquema '{nombre}' de MS3 choca con otro contrato")

    _exigir_campos_siempre_serializados(
        componentes["schemas"], [modelo for _, modelo in _CONTRATOS] + list(CONTRATOS_MS3)
    )
    _documentar_bloqueo_login(esquema)
    agregar_ejemplos_ordenes(esquema, prefijo="/api")
    agregar_ejemplos_gateway(esquema)
    app.openapi_schema = esquema
    return esquema
