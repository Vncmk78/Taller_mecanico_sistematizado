"""Endpoints propios de la Gateway: índice y healthcheck.

Son los únicos endpoints que responde la Gateway por sí misma; todo lo demás
bajo `/api/*` se reenvía a un microservicio.
"""
from __future__ import annotations

from fastapi import APIRouter

from gateway.config import settings

router = APIRouter()


@router.get("/", tags=["info"])
async def indice() -> dict[str, object]:
    """Descripción de la Gateway y de los microservicios que enruta."""
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


@router.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    """El proceso de la Gateway está vivo (no consulta a los microservicios)."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}
