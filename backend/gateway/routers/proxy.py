"""Reenvío (proxy) de `/api/*` hacia los microservicios.

Captura cualquier petición bajo `/api/` que la Gateway no responda por sí
misma (índice y healthcheck) y la reenvía al microservicio que indica la
tabla de enrutamiento (`gateway.rutas`). La lógica no cambia respecto al
proxy original: solo se movió a un router propio.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from gateway.config import settings
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
)
async def proxy(ruta: str, request: Request) -> Response:
    """Reenvía la petición `/api/*` al microservicio que corresponda."""
    primer_segmento = ruta.split("/", 1)[0].lower()
    base = resolver_microservicio(ruta)
    if base is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"No hay microservicio para '/{primer_segmento}'"},
        )

    destino = f"{base.rstrip('/')}/{ruta}"
    if request.url.query:
        destino = f"{destino}?{request.url.query}"

    cabeceras = {
        clave: valor
        for clave, valor in request.headers.items()
        if clave.lower() not in _CABECERAS_PROHIBIDAS
    }
    cuerpo = await request.body()

    try:
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as cliente:
            respuesta = await cliente.request(
                method=request.method,
                url=destino,
                headers=cabeceras,
                content=cuerpo,
            )
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "detail": (
                    f"Microservicio inalcanzable en '{base}' "
                    f"(error {type(exc).__name__})"
                )
            },
        )

    tipo_contenido = respuesta.headers.get("content-type")
    cabeceras_respuesta = {"content-type": tipo_contenido} if tipo_contenido else {}
    return Response(
        content=respuesta.content,
        status_code=respuesta.status_code,
        headers=cabeceras_respuesta,
    )