"""API del microservicio MS1: Autenticación y Usuarios."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
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


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """El proceso está vivo."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}


@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """La conexión a la base propia del servicio responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "servicio": settings.SERVICE_NAME, "database": "ok"}
