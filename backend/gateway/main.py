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
from gateway.routers import health, proxy

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

# Reenvío de `/api/*` a los microservicios. Va al final: captura todo camino
# bajo `/api/` y no debe tapar endpoints propios como `/api/health`.
app.include_router(proxy.router)