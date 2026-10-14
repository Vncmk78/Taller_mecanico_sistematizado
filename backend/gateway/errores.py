"""Formato común de errores de la API Gateway.

Toda respuesta de error generada por la Gateway usa el mismo cuerpo
(`ErrorRespuesta` de `gateway.esquemas`) y deja la cabecera `X-Request-ID`,
para que el frontend pueda leer `response.data.detail` y rastrear una petición
por su identificador. Los errores provenientes de los microservicios no se
modifican: pasan tal cual.

El error 500 no se resuelve con un manejador de `Exception` de Starlette,
porque ese ejecuta fuera de CORS y el navegador bloquearía la respuesta.
Se captura en `ManejoErroresMiddleware`, que se monta por dentro de CORS
para que la respuesta de error también lleve `Access-Control-Allow-Origin`
(orden: RequestId -> CORS -> ManejoErrores).
"""
from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from gateway.esquemas import DetalleError, ErrorRespuesta

logger = logging.getLogger("gateway")

# Códigos del catálogo de errores de la Gateway (Semana 2 y Semana 4).
RUTA_NO_ENCONTRADA = "RUTA_NO_ENCONTRADA"
METODO_NO_PERMITIDO = "METODO_NO_PERMITIDO"
MICROSERVICIO_INALCANZABLE = "MICROSERVICIO_INALCANZABLE"
TIEMPO_AGOTADO = "TIEMPO_AGOTADO"
GATEWAY_SATURADA = "GATEWAY_SATURADA"
ERROR_MICROSERVICIO = "ERROR_MICROSERVICIO"
ERROR_INTERNO = "ERROR_INTERNO"
# El body supera el límite por prefijo (checklist 4.2); se responde sin leerlo
# ni llamar al microservicio.
CUERPO_DEMASIADO_GRANDE = "CUERPO_DEMASIADO_GRANDE"
# Estado HTTP no previsto (por ejemplo, un 400 lanzado por la propia app).
ERROR_HTTP = "ERROR_HTTP"

# Mapeo de estado HTTP -> código del catálogo.
_CODIGOS_POR_ESTADO: dict[int, str] = {
    404: RUTA_NO_ENCONTRADA,
    405: METODO_NO_PERMITIDO,
    413: CUERPO_DEMASIADO_GRANDE,
    502: MICROSERVICIO_INALCANZABLE,
    503: GATEWAY_SATURADA,
    504: TIEMPO_AGOTADO,
    500: ERROR_INTERNO,
}

# Detalles legibles para el frontend; reemplazan los mensajes en inglés que
# genera FastAPI ("Not Found", "Method Not Allowed").
MENSAJE_RUTA_NO_ENCONTRADA = "Ruta no encontrada"
MENSAJE_METODO_NO_PERMITIDO = "Método no permitido"
# Genérico: no revela el límite exacto del prefijo.
MENSAJE_CUERPO_DEMASIADO_GRANDE = "El cuerpo de la petición supera el tamaño permitido"
_DETALLES_POR_ESTADO: dict[int, str] = {
    404: MENSAJE_RUTA_NO_ENCONTRADA,
    405: MENSAJE_METODO_NO_PERMITIDO,
    413: MENSAJE_CUERPO_DEMASIADO_GRANDE,
}

_MENSAJE_ERROR_INTERNO = "Ocurrió un error inesperado en la Gateway."
MENSAJE_SERVICIO_CAIDO = "El servicio no está disponible. Intente más tarde."
MENSAJE_TIEMPO_AGOTADO = (
    "El servicio tardó demasiado en responder. Intente más tarde."
)
MENSAJE_GATEWAY_SATURADA = "La Gateway está ocupada. Intente más tarde."
MENSAJE_ERROR_MICROSERVICIO = "El servicio respondió con un error inesperado."
MENSAJE_CONTENT_LENGTH_INVALIDA = "La cabecera Content-Length es inválida"


def mapear_error_httpx(exc: httpx.RequestError) -> tuple[int, str, str]:
    """Mapea un fallo de red de HTTPX a `(estado, código, detalle)`.

    Se evalúan primero las clases concretas: `ConnectTimeout`, `ReadTimeout`,
    `WriteTimeout` y `PoolTimeout` son subclases de `TimeoutException`, y
    `ConnectError` de `NetworkError`; un chequeo por superclase no alcanza
    para distinguirlos.
    """
    if isinstance(exc, httpx.PoolTimeout):
        return 503, GATEWAY_SATURADA, MENSAJE_GATEWAY_SATURADA
    if isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout)):
        return 504, TIEMPO_AGOTADO, MENSAJE_TIEMPO_AGOTADO
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return 502, MICROSERVICIO_INALCANZABLE, MENSAJE_SERVICIO_CAIDO
    return 502, MICROSERVICIO_INALCANZABLE, MENSAJE_SERVICIO_CAIDO


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def respuesta_error(
    request: Request,
    *,
    estado: int,
    codigo: str,
    detalle: str,
) -> JSONResponse:
    """Construye una respuesta de error con el formato común.

    El `request_id` se agrega aquí (y no solo en el middleware) porque el
    manejador HTTP corre fuera de la cadena de middlewares y el middleware no
    alcanzaría a inyectarle la cabecera.
    """
    request_id = _request_id(request)
    cuerpo = ErrorRespuesta(
        detail=detalle,
        error=DetalleError(
            codigo=codigo,
            estado=estado,
            ruta=request.url.path,
            request_id=request_id,
        ),
    )
    return JSONResponse(
        status_code=estado,
        content=cuerpo.model_dump(),
        headers={"X-Request-ID": request_id},
    )


class ManejoErroresMiddleware:
    """Captura errores no controlados y los convierte al formato común.

    Vive por dentro de CORS: la respuesta `500` que genera aquí sale con
    `Access-Control-Allow-Origin`, cosa que no ocurre con un manejador de
    `Exception` de Starlette (que se resuelve por fuera de CORS).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        except StarletteHTTPException:
            raise
        except Exception:
            request = Request(scope)
            logger.exception(
                "Error no controlado en %s (request_id=%s)",
                request.url.path,
                getattr(request.state, "request_id", "-"),
            )
            respuesta = respuesta_error(
                request,
                estado=500,
                codigo=ERROR_INTERNO,
                detalle=_MENSAJE_ERROR_INTERNO,
            )
            await respuesta(scope, receive, send)


def registrar_manejadores(app: FastAPI) -> None:
    """Registra el manejador de errores HTTP (404, 405 y otros instancias)."""

    @app.exception_handler(StarletteHTTPException)
    async def manejar_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return respuesta_error(
            request,
            estado=exc.status_code,
            codigo=_CODIGOS_POR_ESTADO.get(exc.status_code, ERROR_HTTP),
            detalle=_DETALLES_POR_ESTADO.get(exc.status_code, str(exc.detail)),
        )