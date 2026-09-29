"""Punto de entrada del microservicio de Presupuestos, Repuestos y Proveedores (MS3)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.infrastructure.config import settings
from app.infrastructure.db.session import engine

app = FastAPI(
    title="MS3 - Presupuestos, Repuestos y Proveedores",
    description=(
        "Microservicio de presupuestos, repuestos, proveedores e inventario "
        "del Taller Mecánico Sistematizado."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check():
    """El proceso responde."""
    return {"status": "ok", "service": "presupuestos-service"}


@app.get("/health/db", tags=["Health"])
def health_db():
    """La base de datos del servicio responde."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "db": "reachable"}
