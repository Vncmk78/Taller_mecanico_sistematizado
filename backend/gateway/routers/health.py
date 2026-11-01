"""Endpoints propios de la Gateway: índice y healthchecks.

Son los únicos endpoints que responde la Gateway por sí misma; todo lo demás
bajo `/api/*` se reenvía a un microservicio.

`/api/health` responde solo por la Gateway (lo usa Vercel) y no consulta a los
microservicios. `/api/health/servicios` consulta el `/health/db` de los cuatro
microservicios en paralelo con el cliente HTTPX compartido y devuelve el estado
de cada uno (decisión 8 de `docs/estudio-httpx-proxy.md`).

`/api/health/servicios/{servicio}` (Semana 7, decisión R5 de
`docs/estudio-resiliencia-timeouts-retries.md`) es el diagnóstico de UN
servicio: comprueba por separado el proceso (`/health`), la base (`/health/db`)
y, en MS4, el almacenamiento (`/health/storage`), con la latencia de cada uno,
el timeout que la Gateway le aplica y sus prefijos públicos. Así se distingue
"el servicio no levanta" de "levanta pero su base o su almacenamiento fallan".
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gateway.cliente_http import obtener_cliente, timeout_para
from gateway.config import settings
from gateway.errores import RUTA_NO_ENCONTRADA, respuesta_error
from gateway.rutas import (
    MICROSERVICIOS,
    MICROSERVICIOS_POR_NOMBRE,
    Microservicio,
    prefijos_publicos,
)

logger = logging.getLogger("gateway")

router = APIRouter()

# Nombre público de cada microservicio -> URL base. Sale del catálogo de
# `gateway.rutas`, el mismo que usa el proxy: no hay dos listas que mantener.
SERVICIOS: dict[str, str] = {servicio.nombre: servicio.url for servicio in MICROSERVICIOS}


@router.get("/", tags=["info"])
async def indice() -> dict[str, object]:
    """Descripción de la Gateway y de los prefijos `/api/*` que enruta."""
    return {
        "servicio": "SGTM — API Gateway",
        "estado": "operativo",
        "microservicios": {
            servicio.nombre: prefijos_publicos(servicio)
            for servicio in MICROSERVICIOS
        },
        "ejemplos": [
            "/api/health",
            "/api/health/servicios",
            "/api/auth/login",
            "/api/auth/me",
            "/api/vehiculos",
            "/api/ordenes",
            "/api/presupuestos",
            "/api/repuestos",
            "/api/inventario/alertas",
            "/api/evidencias?orden_id=31",
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


@router.get(
    "/api/health/servicios/{servicio}",
    tags=["health"],
    responses={
        200: {"description": "Todas las comprobaciones del servicio respondieron OK."},
        404: {"description": "Servicio desconocido (RUTA_NO_ENCONTRADA)."},
        503: {"description": "Alguna comprobación falló: `estado` es `degradado` o `caido`."},
    },
)
async def diagnostico_servicio(servicio: str, request: Request) -> JSONResponse:
    """Diagnóstico de un microservicio: proceso, base y (MS4) almacenamiento.

    `servicio` es el nombre público: `ms1_auth`, `ms2_taller`,
    `ms3_presupuestos` o `ms4_evidencias`. Las comprobaciones corren en
    paralelo, cada una con `GATEWAY_HEALTH_TIMEOUT_SECONDS`. El body nunca
    expone URLs internas: el detalle de cada fallo queda en el log.
    """
    destino = MICROSERVICIOS_POR_NOMBRE.get(servicio.lower())
    if destino is None:
        return respuesta_error(
            request,
            estado=404,
            codigo=RUTA_NO_ENCONTRADA,
            detalle="Servicio desconocido. Use ms1_auth, ms2_taller, ms3_presupuestos o ms4_evidencias.",
        )

    resultados = await asyncio.gather(
        *(
            _sondear(destino.nombre, destino.url, camino)
            for _, camino in destino.comprobaciones
        )
    )
    comprobaciones = {
        nombre: resultado
        for (nombre, _), resultado in zip(destino.comprobaciones, resultados)
    }
    estado = _estado_general(comprobaciones)
    return JSONResponse(
        content={
            "servicio": destino.nombre,
            "descripcion": destino.descripcion,
            "estado": estado,
            "comprobaciones": comprobaciones,
            "prefijos": prefijos_publicos(destino),
            "timeouts": _timeouts_publicos(destino),
            "comprobado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        status_code=200 if estado == "ok" else 503,
        headers={"Cache-Control": "no-store"},
    )


def _estado_general(comprobaciones: dict[str, dict[str, object]]) -> str:
    """`ok` si todo responde; `caido` si ni el proceso responde; si no, `degradado`."""
    if all(c["estado"] == "ok" for c in comprobaciones.values()):
        return "ok"
    if comprobaciones.get("proceso", {}).get("estado") in {"caido", "tiempo_agotado"}:
        return "caido"
    return "degradado"


def _timeouts_publicos(servicio: Microservicio) -> dict[str, float]:
    """Timeouts que la Gateway aplica al servicio (segundos), para diagnóstico."""
    timeout = timeout_para(servicio.prefijos[0])
    return {
        "conexion": timeout.connect,
        "lectura": timeout.read,
        "escritura": timeout.write,
        "health": settings.HEALTH_TIMEOUT_SECONDS,
    }


async def _sondear(nombre: str, base: str, camino: str) -> dict[str, object]:
    """Consulta `{base}{camino}` y devuelve `{estado, latencia_ms, codigo_http?}`.

    Estados: `ok` (200), `error` (respondió con otro código; incluye
    `codigo_http`), `tiempo_agotado` y `caido` (sin conexión). Nunca lanza.
    """
    inicio = time.perf_counter()
    try:
        respuesta = await obtener_cliente().get(
            f"{base.rstrip('/')}{camino}",
            timeout=httpx.Timeout(settings.HEALTH_TIMEOUT_SECONDS),
        )
    except httpx.TimeoutException as exc:
        logger.warning(
            "Diagnóstico: %s %s superó el timeout (%s)", nombre, camino, type(exc).__name__
        )
        return {"estado": "tiempo_agotado"}
    except httpx.RequestError as exc:
        logger.warning(
            "Diagnóstico: %s %s no respondió (%s)", nombre, camino, type(exc).__name__
        )
        return {"estado": "caido"}
    except Exception:
        logger.exception("Diagnóstico: error inesperado al consultar %s %s", nombre, camino)
        return {"estado": "caido"}

    latencia_ms = int(round((time.perf_counter() - inicio) * 1000))
    if respuesta.status_code == 200:
        return {"estado": "ok", "latencia_ms": latencia_ms}
    return {
        "estado": "error",
        "latencia_ms": latencia_ms,
        "codigo_http": respuesta.status_code,
    }


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