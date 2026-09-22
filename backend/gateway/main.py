"""API Gateway: única puerta de entrada al backend del SGTM.

El cliente web (React) y la app móvil llaman a `/api/*` en esta Gateway; aquí
se enruta cada petición al microservicio correspondiente sin exponer la red
interna del backend. La Gateway solo reenvía (proxy) y no conoce reglas de
negocio, preservando el aislamiento entre microservicios.

Fuente: Arquitectura SGTM (API Gateway + 4 microservicios FastAPI, cada uno
con su propia base PostgreSQL).
"""
from __future__ import annotations

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from gateway.config import settings
from gateway.routers import health

app = FastAPI(title="SGTM — API Gateway", version="0.1.0")

# CORS se resuelve en la Gateway (punto único de entrada), no en los
# microservicios: los navegadores exigen estas cabeceras para consumir la API
# desde otro origen (frontend web, Expo Web, herramientas de prueba).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints propios de la Gateway (índice y healthcheck).
app.include_router(health.router)

# Primer segmento de la ruta -> URL base del microservicio destino.
RUTAS: dict[str, str] = {
    "auth": settings.MS1_URL,
    "vehiculos": settings.MS2_URL,
    "vehiculo": settings.MS2_URL,
    "ordenes": settings.MS2_URL,
    "orden": settings.MS2_URL,
    "clientes": settings.MS2_URL,
    "mecanicos": settings.MS2_URL,
    "presupuestos": settings.MS3_URL,
    "presupuesto": settings.MS3_URL,
    "repuestos": settings.MS3_URL,
    "proveedores": settings.MS3_URL,
    "inventario": settings.MS3_URL,
    "evidencias": settings.MS4_URL,
    "evidencia": settings.MS4_URL,
}

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


@app.api_route(
    "/api/{ruta:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(ruta: str, request: Request) -> Response:
    """Reenvía la petición `/api/*` al microservicio que corresponda."""
    primer_segmento = ruta.split("/", 1)[0].lower()
    base = RUTAS.get(primer_segmento)
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