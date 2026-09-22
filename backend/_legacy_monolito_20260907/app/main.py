"""Punto de entrada mínimo de la API.

Solo incluye healthchecks para verificar que la app levanta y que la conexión
a la base de datos funciona. Los endpoints de negocio los agregan los demás
integrantes en sus respectivos microservicios/rutas.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

app = FastAPI(title="Taller Mecánico API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"database": "ok"}
