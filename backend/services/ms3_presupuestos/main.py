"""API del microservicio MS3: Presupuestos, Repuestos y Proveedores.

Por ahora solo expone los healthchecks que verifican que el servicio levanta y
que su conexión a PostgreSQL responde. Los endpoints de negocio los agregan los
integrantes responsables de este servicio.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db

app = FastAPI(title="SGTM — MS3: Presupuestos, Repuestos y Proveedores", version="0.1.0")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """El proceso está vivo."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}


@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """La conexión a la base propia del servicio responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "servicio": settings.SERVICE_NAME, "database": "ok"}
