"""API del microservicio MS3: Presupuestos, Repuestos y Proveedores.

Estructura del servicio (Semana 4):

    main.py          app FastAPI, healthchecks y registro de routers
    config.py        variables MS3_* (base de datos y JWT)
    db.py            Base, engine, SessionLocal y get_db propios de MS3
    dependencies.py  autenticación JWT y guard por roles
    routers/         endpoints HTTP (uno por recurso)
    schemas/         contratos Pydantic de entrada/salida
    services/        reglas de negocio y transacciones
    models/          modelos ORM (MER, recuadro "BD MS3")
    alembic/         migraciones propias (0001 → 0003)

Los endpoints de negocio se agregan en routers/ y se registran en ROUTERS.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.routers import ROUTERS

app = FastAPI(
    title="SGTM — MS3: Presupuestos, Repuestos y Proveedores",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Healthchecks del servicio (proceso y base)."},
        {"name": "presupuestos", "description": "Presupuestos versionados y decisión del cliente (en desarrollo)."},
        {"name": "repuestos", "description": "Catálogo de repuestos y stock (en desarrollo)."},
        {"name": "proveedores", "description": "Proveedores de repuestos (en desarrollo)."},
        {"name": "inventario", "description": "Movimientos de inventario y umbrales (en desarrollo)."},
    ],
)

for router in ROUTERS:
    app.include_router(router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """El proceso está vivo."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}


@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """La conexión a la base propia del servicio responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "servicio": settings.SERVICE_NAME, "database": "ok"}
