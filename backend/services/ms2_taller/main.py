"""API del microservicio MS2: Vehículos y Órdenes de Trabajo."""
from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.ms2_taller.config import settings
from services.ms2_taller.db import get_db
from services.ms2_taller.dependencies import resolver_cliente_actual
from services.ms2_taller.routers import crear_router_vehiculos, router_ordenes
from shared.openapi_ordenes import agregar_ejemplos_ordenes

app = FastAPI(title="SGTM — MS2: Vehículos y Órdenes de Trabajo", version="0.1.0")
app.include_router(crear_router_vehiculos(resolver_cliente_actual))
app.include_router(router_ordenes)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """El proceso está vivo."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}


@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """La conexión a la base propia del servicio responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "servicio": settings.SERVICE_NAME, "database": "ok"}


_openapi_original = app.openapi


def openapi_con_ejemplos() -> dict:
    """Conserva la generación nativa y añade documentación común con Gateway."""
    esquema = _openapi_original()
    agregar_ejemplos_ordenes(esquema)
    return esquema


app.openapi = openapi_con_ejemplos
