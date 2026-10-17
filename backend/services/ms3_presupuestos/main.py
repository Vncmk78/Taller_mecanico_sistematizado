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
    alembic/         migraciones propias (0001 → 0004)

Los endpoints de negocio se agregan en routers/ y se registran en ROUTERS.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.integracion_ms2 import DecisionAplicacionPendienteError, ServicioOrdenesNoDisponible
from shared.contratos_decisiones import DecisionAplicacionPendiente
from services.ms3_presupuestos.persistencia import ErrorDePersistencia
from services.ms3_presupuestos.routers import ROUTERS

app = FastAPI(
    title="SGTM — MS3: Presupuestos, Repuestos y Proveedores",
    version="0.1.0",
    # Swagger y ReDoc se sirven abajo con URL RELATIVA al openapi.json: en
    # Vercel el servicio vive bajo /ms3 y "/openapi.json" absoluto cargaba la
    # especificación de la Gateway en vez de la de MS3.
    docs_url=None,
    redoc_url=None,
    # Servidores para "Try it out": "." = mismo prefijo donde se sirve la
    # especificación (/ms3 en Vercel, raíz en local); "/api" = vía Gateway.
    servers=[
        {"url": ".", "description": "Directo al MS3 (/ms3 en Vercel, raíz en local)"},
        {"url": "/api", "description": "A través de la API Gateway (como lo usan web y móvil)"},
    ],
    openapi_tags=[
        {"name": "health", "description": "Healthchecks del servicio (proceso y base)."},
        {"name": "presupuestos", "description": "Presupuesto único por orden: versiones, ítems, envío y decisión del cliente."},
        {"name": "repuestos", "description": "Catálogo de repuestos, stock y alerta de stock bajo."},
        {"name": "proveedores", "description": "Proveedores (distribuidores) de repuestos."},
        {"name": "inventario", "description": "Movimientos de stock (idempotentes), disponibilidad, alertas y umbral general."},
    ],
)

for router in ROUTERS:
    app.include_router(router)


@app.get("/docs", include_in_schema=False)
def _swagger() -> HTMLResponse:
    return get_swagger_ui_html(openapi_url="openapi.json", title=f"{app.title} — Swagger")


@app.get("/redoc", include_in_schema=False)
def _redoc() -> HTMLResponse:
    return get_redoc_html(openapi_url="openapi.json", title=f"{app.title} — ReDoc")


@app.exception_handler(ErrorDePersistencia)
def _error_de_persistencia(_: Request, exc: ErrorDePersistencia) -> JSONResponse:
    """Traduce los errores de la capa de datos a HTTP (404 / 409 / 422 / 500).

    Nunca devuelve SQL ni parámetros: solo el mensaje pensado para el cliente.
    """
    return JSONResponse(status_code=exc.codigo_http, content={"detail": exc.mensaje})


@app.exception_handler(ServicioOrdenesNoDisponible)
def _ms2_no_disponible(_: Request, __: ServicioOrdenesNoDisponible) -> JSONResponse:
    """MS2 no respondió: no se puede confirmar que la orden sea del usuario."""
    return JSONResponse(
        status_code=503,
        content={"detail": "No fue posible validar la orden con el servicio de órdenes"},
    )


@app.exception_handler(DecisionAplicacionPendienteError)
def _decision_aplicacion_pendiente(_: Request, exc: DecisionAplicacionPendienteError) -> JSONResponse:
    respuesta = DecisionAplicacionPendiente(
        detail="La decisión quedó registrada; no se pudo confirmar su aplicación en MS2. "
               "Reintente la misma decisión, sin volver a aprobar ni rechazar.",
        decision_id=exc.decision_id, orden_id=exc.orden_id,
        reintento=f"/api/presupuestos/decisiones/{exc.decision_id}/aplicacion",
        estado_ms2=exc.estado_ms2, detalle_ms2=exc.detalle_ms2,
    )
    return JSONResponse(status_code=503, content=respuesta.model_dump())


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """El proceso está vivo."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}


@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """La conexión a la base propia del servicio responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "servicio": settings.SERVICE_NAME, "database": "ok"}
