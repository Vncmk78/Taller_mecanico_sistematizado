"""Reenvío (proxy) de `/api/*` hacia los microservicios.

Captura cualquier petición bajo `/api/` que la Gateway no responda por sí
misma (índice y healthcheck) y la reenvía al microservicio que indica la tabla
de enrutamiento (`gateway.rutas`), usando el cliente HTTPX compartido
(`gateway.cliente_http`), timeouts por fase y el mapeo de errores de la Semana
4 (decisiones 1 a 6 de `docs/estudio-httpx-proxy.md`).
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

from gateway.cliente_http import obtener_cliente, timeout_para
from gateway.errores import (
    ERROR_MICROSERVICIO,
    MENSAJE_ERROR_MICROSERVICIO,
    MENSAJE_METODO_NO_PERMITIDO,
    MENSAJE_RUTA_NO_ENCONTRADA,
    METODO_NO_PERMITIDO,
    RUTA_NO_ENCONTRADA,
    mapear_error_httpx,
    respuesta_error,
)
from gateway.rutas import resolver_microservicio

logger = logging.getLogger("gateway")

router = APIRouter()

# Cabeceras HTTP que no se reenvían al microservicio (son del salto local) ni
# al cliente (así las reconstruye la Gateway o Starlette).
_CABECERAS_PROHIBIDAS = {
    "host",
    "content-length",
    "connection",
    "transfer-encoding",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "upgrade",
}

# Cabeceras de la respuesta del microservicio que no llegan al cliente: las
# hop-by-hop, las que HTTPX ya procesó (content-encoding: el body viene
# descomprimido) y las que la propia Gateway reconstruye (content-length,
# x-request-id lo pone el middleware; server y date son de la Gateway).
_CABECERAS_RESPUESTA_EXCLUIDAS = _CABECERAS_PROHIBIDAS | {
    "content-encoding",
    "x-request-id",
    "server",
    "date",
}

# 4xx sin JSON que se normalizan con un código del catálogo propio, no con
# ERROR_MICROSERVICIO (decisión 3).
_CATALOGO_NO_JSON: dict[int, tuple[str, str]] = {
    404: (RUTA_NO_ENCONTRADA, MENSAJE_RUTA_NO_ENCONTRADA),
    405: (METODO_NO_PERMITIDO, MENSAJE_METODO_NO_PERMITIDO),
}


@router.api_route(
    "/api/{ruta:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def proxy(ruta: str, request: Request) -> Response:
    """Reenvía la petición `/api/*` al microservicio que corresponda."""
    primer_segmento = ruta.split("/", 1)[0].lower()
    base = resolver_microservicio(ruta)
    if base is None:
        return respuesta_error(
            request,
            estado=404,
            codigo=RUTA_NO_ENCONTRADA,
            detalle=f"No hay microservicio para '/{primer_segmento}'",
        )

    destino = f"{base.rstrip('/')}/{ruta}"
    if request.url.query:
        destino = f"{destino}?{request.url.query}"

    cabeceras = {
        clave: valor
        for clave, valor in request.headers.items()
        if clave.lower() not in _CABECERAS_PROHIBIDAS
    }
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        cabeceras["x-request-id"] = request_id

    # X-Forwarded-*: origen real de la petición, para logs y (más adelante)
    # el límite de frecuencia (checklist 4.4).
    host_original = request.headers.get("host")
    if request.client is not None:
        ip_cliente = request.client.host
        anterior = cabeceras.get("x-forwarded-for")
        cabeceras["x-forwarded-for"] = (
            f"{anterior}, {ip_cliente}" if anterior else ip_cliente
        )
    cabeceras["x-forwarded-proto"] = request.url.scheme
    if host_original and "x-forwarded-host" not in cabeceras:
        cabeceras["x-forwarded-host"] = host_original

    cuerpo = await request.body()

    try:
        respuesta = await obtener_cliente().request(
            method=request.method,
            url=destino,
            headers=cabeceras,
            content=cuerpo,
            timeout=timeout_para(primer_segmento),
        )
    except httpx.RequestError as exc:
        # Solo se loguea el nombre de la excepción y el request_id: nunca la
        # URL interna ni el texto del error.
        logger.warning(
            "Fallo de red hacia el microservicio: %s (request_id=%s)",
            type(exc).__name__,
            request_id,
        )
        estado, codigo, detalle = mapear_error_httpx(exc)
        return respuesta_error(
            request, estado=estado, codigo=codigo, detalle=detalle
        )

    return _construir_respuesta(request, respuesta, base)


def _reescribir_location(request: Request, location: str, base: str) -> str:
    """Traduce un `Location` del microservicio a la URL pública de la Gateway.

    El microservicio conoce su propia URL interna (p. ej. la redirección 307
    de FastAPI por la barra final, o el `Location` de un 201). Reenviarla tal
    cual filtraría la red interna y el cliente no podría seguirla. Como el
    microservicio publica sus rutas sin `/api` (`/vehiculos/...`), se vuelve a
    anteponer `/api` y el origen público de la Gateway.
    """
    base = base.rstrip("/")
    if location.startswith(base + "/") or location == base:
        camino = location[len(base):] or "/"
    elif location.startswith("/") and not location.startswith("//"):
        camino = location
    else:
        return location  # URL externa: no es del microservicio, pasa igual.
    if camino == "/api" or camino.startswith("/api/"):
        return str(request.base_url).rstrip("/") + camino
    return str(request.base_url).rstrip("/") + "/api" + camino


def _construir_respuesta(
    request: Request, respuesta: httpx.Response, base: str
) -> Response:
    """Convierte la respuesta del microservicio en la respuesta al cliente.

    - 2xx/3xx pasan con su body y sus cabeceras.
    - 4xx/5xx con body JSON pasan tal cual (decisión 3).
    - 4xx/5xx sin body JSON se normalizan al formato común, conservando
      `WWW-Authenticate` y `Retry-After`.
    """
    if respuesta.status_code >= 400 and not _tiene_body_json(respuesta):
        return _normalizar_error_no_json(request, respuesta)

    respuesta_cliente = Response(
        content=respuesta.content,
        status_code=respuesta.status_code,
    )
    for clave, valor in respuesta.headers.multi_items():
        if not _cabecera_cliente_permitida(clave):
            continue
        if clave.lower() == "location":
            valor = _reescribir_location(request, valor, base)
        respuesta_cliente.headers.append(clave, valor)
    return respuesta_cliente


def _tiene_body_json(respuesta: httpx.Response) -> bool:
    """True si el contenido es JSON (content-type con 'json' y body que parsea)."""
    if "json" not in respuesta.headers.get("content-type", "").lower():
        return False
    try:
        respuesta.json()
        return True
    except ValueError:
        return False


def _cabecera_cliente_permitida(clave: str) -> bool:
    """Cabeceras de la respuesta del microservicio que sí llegan al cliente."""
    clave_min = clave.lower()
    if clave_min in _CABECERAS_RESPUESTA_EXCLUIDAS:
        return False
    # Las de CORS las pone la propia Gateway; duplicarlas rompe el navegador.
    if clave_min.startswith("access-control-"):
        return False
    return True


def _normalizar_error_no_json(request: Request, respuesta: httpx.Response) -> Response:
    """Reemplaza un 4xx/5xx sin JSON por el formato común de la Gateway."""
    request_id = getattr(request.state, "request_id", None)
    logger.warning(
        "Microservicio respondió %s sin cuerpo JSON (request_id=%s)",
        respuesta.status_code,
        request_id,
    )
    codigo, detalle = _CATALOGO_NO_JSON.get(
        respuesta.status_code,
        (ERROR_MICROSERVICIO, MENSAJE_ERROR_MICROSERVICIO),
    )
    error = respuesta_error(
        request,
        estado=respuesta.status_code,
        codigo=codigo,
        detalle=detalle,
    )
    for cabecera in ("www-authenticate", "retry-after"):
        valor = respuesta.headers.get(cabecera)
        if valor:
            error.headers[cabecera] = valor
    return error
