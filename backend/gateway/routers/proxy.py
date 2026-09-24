"""Reenvío (proxy) de `/api/*` hacia los microservicios.

Captura cualquier petición bajo `/api/` que la Gateway no responda por sí
misma (índice y healthcheck) y la reenvía al microservicio que indica la
tabla de enrutamiento (`gateway.rutas`). La lógica no cambia respecto al
proxy original: solo se movió a un router propio.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

from gateway.config import settings
from gateway.errores import (
    MENSAJE_SERVICIO_CAIDO,
    MICROSERVICIO_INALCANZABLE,
    RUTA_NO_ENCONTRADA,
    respuesta_error,
)
from gateway.rutas import resolver_microservicio

router = APIRouter()

# Cabeceras HTTP que no deben reenviarse al microservicio (son del salto local).
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
    cuerpo = await request.body()

    try:
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as cliente:
            respuesta = await cliente.request(
                method=request.method,
                url=destino,
                headers=cabeceras,
                content=cuerpo,
            )
    except httpx.HTTPError:
        return respuesta_error(
            request,
            estado=502,
            codigo=MICROSERVICIO_INALCANZABLE,
            detalle=MENSAJE_SERVICIO_CAIDO,
        )

    tipo_contenido = respuesta.headers.get("content-type")
    cabeceras_respuesta = {"content-type": tipo_contenido} if tipo_contenido else {}
    return Response(
        content=respuesta.content,
        status_code=respuesta.status_code,
        headers=cabeceras_respuesta,
    )