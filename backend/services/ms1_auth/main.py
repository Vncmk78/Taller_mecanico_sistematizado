"""API del microservicio MS1: Autenticación y Usuarios."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.ms1_auth.config import settings
from services.ms1_auth.db import get_db
from services.ms1_auth.routers import router_auth, router_notificaciones

from services.ms1_auth.routers.entregas_notificaciones import router as router_entregas
from services.ms1_auth.services.worker_notificaciones import ejecutar_worker
from shared.correlacion import MiddlewareCorrelacion
from shared.correlacion import configurar_logs as configurar_logs_correlacion


@asynccontextmanager
async def lifespan(_app):
    tarea = asyncio.create_task(ejecutar_worker()) if settings.NOTIFICATION_WORKER_ENABLED else None
    try:
        yield
    finally:
        if tarea is not None:
            tarea.cancel()
            try:
                await tarea
            except asyncio.CancelledError:
                pass


app = FastAPI(lifespan=lifespan, title="SGTM — MS1: Autenticación y Usuarios", version="0.1.0")

# Semana 10 (SCRUM-582): toma el X-Request-ID que reenvía la Gateway, lo
# devuelve en toda respuesta y deja una línea de log por petición con ese ID.
configurar_logs_correlacion()
app.add_middleware(MiddlewareCorrelacion, servicio="ms1_auth")
app.include_router(router_auth)
app.include_router(router_notificaciones)
app.include_router(router_entregas)
from services.ms1_auth.routers.avisos_ms3 import router as router_avisos_ms3
app.include_router(router_avisos_ms3)


# Pydantic incluye el valor recibido (`input`) en cada error de validación. En
# MS1 ese valor puede ser la contraseña o el token del dispositivo, y el `422`
# se reenvía tal cual al cliente (y a cualquier registro intermedio que guarde
# cuerpos). Se enmascaran solo los campos secretos; el resto del detalle de
# validación se conserva.
_CAMPOS_SECRETOS = frozenset(
    {"password", "token", "contrasena", "secreto", "secret"}
)


def _enmascarar_secretos(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {
            clave: (
                "***"
                if str(clave).lower() in _CAMPOS_SECRETOS
                else _enmascarar_secretos(contenido)
            )
            for clave, contenido in valor.items()
        }
    if isinstance(valor, list):
        return [_enmascarar_secretos(contenido) for contenido in valor]
    return valor


def _error_sin_secretos(error: dict[str, Any]) -> dict[str, Any]:
    """Enmascara el valor cuando el error apunta a un campo secreto."""
    if "input" not in error:
        return error
    ubicacion = error.get("loc", ())
    campo_secreto = any(str(parte).lower() in _CAMPOS_SECRETOS for parte in ubicacion)
    # Un campo faltante no refleja su valor: su `input` es el cuerpo recibido,
    # que se enmascara por claves para no ocultar el resto del diagnóstico.
    if campo_secreto and error.get("type") != "missing":
        return {**error, "input": "***"}
    return {**error, "input": _enmascarar_secretos(error["input"])}


@app.exception_handler(RequestValidationError)
async def validacion_sin_secretos(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errores = [_error_sin_secretos(error) for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errores)})


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """El proceso está vivo."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}


@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """La conexión a la base propia del servicio responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "servicio": settings.SERVICE_NAME, "database": "ok"}
