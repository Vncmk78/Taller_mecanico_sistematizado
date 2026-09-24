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

app = FastAPI(title="SGTM — API Gateway", version="0.1.0")

# CORS: el navegador exige `Access-Control-Allow-Origin` cuando el frontend
# (React en Vercel, app móvil) y la Gateway están en orígenes distintos; sin
# esta cabecera el preflight falla y F12 muestra "CORS policy ... no
# Access-Control-Allow-Origin". Se permiten los orígenes del `settings` (que
# incluyen el Vite de desarrollo y el dominio de producción) y cualquier
# preview de Vercel.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https://[a-z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/", tags=["info"])
async def indice() -> dict[str, object]:
    """Descripción de la Gateway y sus rutas."""
    return {
        "servicio": "SGTM — API Gateway",
        "estado": "operativo",
        "microservicios": {
            "ms1_auth": settings.MS1_URL,
            "ms2_taller": settings.MS2_URL,
            "ms3_presupuestos": settings.MS3_URL,
            "ms4_evidencias": settings.MS4_URL,
        },
        "ejemplos": [
            "/api/health",
            "/api/auth/login",
            "/api/auth/me",
            "/api/vehiculos",
        ],
    }


@app.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    """El proceso de la Gateway está vivo."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}


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