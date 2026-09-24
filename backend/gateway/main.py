"""API Gateway: única puerta de entrada al backend del SGTM.

El cliente web (React) y la app móvil llaman a `/api/*` en esta Gateway; aquí
se enruta cada petición al microservicio correspondiente sin exponer la red
interna del backend. La Gateway solo reenvía (proxy) y no conoce reglas de
negocio, preservando el aislamiento entre microservicios.

Fuente: Arquitectura SGTM (API Gateway + 4 microservicios FastAPI, cada uno
con su propia base PostgreSQL).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.config import settings
from gateway.errores import ManejoErroresMiddleware, registrar_manejadores
from gateway.middleware import RequestIdMiddleware
from gateway.openapi import construir_openapi
from gateway.routers import health, proxy

app = FastAPI(title="SGTM — API Gateway", version="0.1.0")

# El Swagger por defecto solo mostraría /api/{ruta}; se reescribe para
# documentar los contratos reales de MS1 y MS2 (ver gateway/openapi.py).
app.openapi = lambda: construir_openapi(app)

# Orden de los middlewares (el último agregado es el más externo):
# RequestId (más afuera) -> CORS -> ManejoErrores (más adentro).
# El middleware de errores va por dentro de CORS para que el 500 también salga
# con Access-Control-Allow-Origin (un handler de Exception correría afuera).
app.add_middleware(ManejoErroresMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIdMiddleware)

# Formato común de errores: 404, 405 y errores no controlados (500).
registrar_manejadores(app)

# Endpoints propios de la Gateway (índice y healthcheck).
app.include_router(health.router)

# Reenvío de `/api/*` a los microservicios. Va al final: captura todo camino
# bajo `/api/` y no debe tapar endpoints propios como `/api/health`.
app.include_router(proxy.router)