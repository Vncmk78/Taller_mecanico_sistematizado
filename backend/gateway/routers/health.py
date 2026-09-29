"""Endpoints propios de la Gateway: índice y healthchecks.

Son los únicos endpoints que responde la Gateway por sí misma; todo lo demás
bajo `/api/*` se reenvía a un microservicio.

`/api/health` responde solo por la Gateway (lo usa Vercel) y no consulta a los
microservicios. `/api/health/servicios` consulta el `/health/db` de los cuatro
microservicios en paralelo con el cliente HTTPX compartido y devuelve el estado
de cada uno (decisión 8 de `docs/estudio-httpx-proxy.md`).
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from gateway.cliente_http import obtener_cliente
from gateway.config import settings
from gateway.rutas import RUTAS

logger = logging.getLogger("gateway")

router = APIRouter()

# Nombre público de cada microservicio -> URL base (se leen de la configuración).
SERVICIOS: dict[str, str] = {
    "ms1_auth": settings.MS1_URL,
    "ms2_taller": settings.MS2_URL,
    "ms3_presupuestos": settings.MS3_URL,
    "ms4_evidencias": settings.MS4_URL,
}


@router.get("/", tags=["info"])
async def indice() -> dict[str, object]:
    """Descripción de la Gateway y de los prefijos `/api/*` que enruta."""
    return {
        "servicio": "SGTM — API Gateway",
        "estado": "operativo",
        "microservicios": {
            nombre: _prefijos_publicos(base)
            for nombre, base in SERVICIOS.items()
        },
        "ejemplos": [
            "/api/health",
            "/api/health/servicios",
            "/api/auth/login",
            "/api/auth/me",
            "/api/vehiculos",
        ],
    }


@router.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    """El proceso de la Gateway está vivo (no consulta a los microservicios)."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}


@router.get("/api/health/servicios", tags=["health"])
async def health_servicios() -> JSONResponse:
    """Estado de los cuatro microservicios (`/health/db` en paralelo).

    200 con `status: ok` si los cuatro responden; 503 con `status: degradado`
    si alguno falla. El body no expone URLs internas.
    """
    estados = await asyncio.gather(
        *(_consultar(nombre, base) for nombre, base in SERVICIOS.items())
    )
    servicios = dict(zip(SERVICIOS, estados))
    todos_ok = all(estado["estado"] == "ok" for estado in estados)
    return JSONResponse(
        content={
            "status": "ok" if todos_ok else "degradado",
            "gateway": "ok",
            "servicios": servicios,
        },
        status_code=200 if todos_ok else 503,
        headers={"Cache-Control": "no-store"},
    )


def _prefijos_publicos(base: str) -> list[str]:
    """Prefijos `/api/*` que la tabla de rutas enruta hacia `base`, ordenados."""
    return sorted(
        f"/api/{prefijo}"
        for prefijo, destino in RUTAS.items()
        if destino == base
    )


async def _consultar(nombre: str, base: str) -> dict[str, object]:
    """Consulta `/health/db` del servicio y devuelve su estado.

    Nunca lanza hacia afuera: los fallos de red se traducen a un estado y quedan
    en el log del servidor (con el nombre del servicio y el tipo de excepción),
    sin exponer URLs internas en la respuesta.
    """
    inicio = time.perf_counter()
    try:
        respuesta = await obtener_cliente().get(
            f"{base.rstrip('/')}/health/db",
            timeout=httpx.Timeout(settings.HEALTH_TIMEOUT_SECONDS),
        )
    except httpx.TimeoutException as exc:
        logger.warning(
            "Health: %s superó el timeout de health check (%s)",
            nombre,
            type(exc).__name__,
        )
        return {"estado": "tiempo_agotado"}
    except httpx.RequestError as exc:
        logger.warning(
            "Health: %s no respondió al health check (%s)",
            nombre,
            type(exc).__name__,
        )
        return {"estado": "caido"}
    except Exception:
        logger.exception("Health: error inesperado al consultar %s", nombre)
        return {"estado": "caido"}

    latencia_ms = int(round((time.perf_counter() - inicio) * 1000))
    if respuesta.status_code == 200:
        return {"estado": "ok", "latencia_ms": latencia_ms}
    return {
        "estado": "sin_base",
        "latencia_ms": latencia_ms,
        "codigo_http": respuesta.status_code,
    }