"""API del microservicio MS3: Presupuestos, Repuestos y Proveedores.

Estructura del servicio (Semana 4):

    main.py          app FastAPI, healthchecks y registro de routers
    config.py        variables MS3_* (base de datos y JWT)
    db.py            Base, engine, SessionLocal y get_db propios de MS3
    dependencies.py  autenticación JWT, guard por roles y unidad de trabajo
    persistencia/    repositorios, unidad de trabajo y errores de la base
    routers/         endpoints HTTP (uno por recurso)
    schemas/         contratos Pydantic de entrada/salida
    services/        reglas de negocio y transacciones
    models/          modelos ORM (MER, recuadro "BD MS3")
    alembic/         migraciones propias (0001 → 0003)

Los endpoints de negocio se agregan en routers/ y se registran en ROUTERS.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.persistencia import ErrorDePersistencia
from services.ms3_presupuestos.routers import ROUTERS

app = FastAPI(
    title="SGTM — MS3: Presupuestos, Repuestos y Proveedores",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Healthchecks del servicio (proceso y base)."},
        {"name": "presupuestos", "description": "Presupuesto único por orden con versiones e ítems (repuestos y mano de obra)."},
        {"name": "repuestos", "description": "Catálogo de repuestos y stock (en desarrollo)."},
        {"name": "proveedores", "description": "Proveedores de repuestos (en desarrollo)."},
        {"name": "inventario", "description": "Movimientos de inventario y umbrales (en desarrollo)."},
    ],
)

for router in ROUTERS:
    app.include_router(router)


@app.exception_handler(ErrorDePersistencia)
def _error_de_persistencia(_: Request, exc: ErrorDePersistencia) -> JSONResponse:
    """Traduce los errores de la capa de datos a HTTP (404 / 409 / 422 / 500).

    Nunca devuelve SQL ni parámetros: solo el mensaje pensado para el cliente.
    """
    return JSONResponse(status_code=exc.codigo_http, content={"detail": exc.mensaje})


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """El proceso está vivo."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}


@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """La conexión a la base propia del servicio responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "servicio": settings.SERVICE_NAME, "database": "ok"}
