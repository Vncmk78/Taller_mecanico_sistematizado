"""API del microservicio MS4: Evidencia Multimedia.

Expone los healthchecks que verifican que el servicio levanta, que su conexiÃ³n a
PostgreSQL responde y que el bucket S3/MinIO de evidencias responde, mÃ¡s los
endpoints de negocio de recepciÃ³n y consulta de evidencias (mÃ³dulos en
routers/).
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.ms4_evidencias.config import settings
from services.ms4_evidencias.db import get_db
from services.ms4_evidencias.routers import ROUTERS
from services.ms4_evidencias.services.registro import (
    MiddlewareRegistro,
    configurar_logs,
)
from services.ms4_evidencias.services.almacenamiento import (
    crear_cliente_s3,
    verificar_bucket,
)

app = FastAPI(
    title="SGTM â€” MS4: Evidencia Multimedia",
    version="0.1.0",
    openapi_tags=[
        {
            "name": "health",
            "description": "Healthchecks del servicio (proceso, base y almacenamiento).",
        },
        {
            "name": "evidencias",
            "description": "Subida de fotos/videos y consulta: listado por orden, detalle y descarga con URL prefirmada.",
        },
    ],
)

for router in ROUTERS:
    app.include_router(router)

# Log de cada solicitud con request_id, estado y duraciÃ³n, sin cabeceras, body
# ni query string (checklist 5.5; services/registro.py).
configurar_logs(settings.LOG_LEVEL)
app.add_middleware(MiddlewareRegistro)

MENSAJE_ERROR_INTERNO = "Error interno del servicio de evidencias"


@app.exception_handler(Exception)
async def error_no_controlado(request: Request, exc: Exception) -> JSONResponse:
    """Cualquier excepciÃ³n no prevista responde 500 con un mensaje genÃ©rico.

    El body nunca lleva el mensaje de la excepciÃ³n, el traceback, el bucket, la
    clave del objeto ni el endpoint del almacenamiento (checklist 5.5). Las
    HTTPException y los 422 de validaciÃ³n de FastAPI tienen sus propios
    manejadores y no pasan por aquÃ­.
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": MENSAJE_ERROR_INTERNO},
    )


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """El proceso estÃ¡ vivo."""
    return {"status": "ok", "servicio": settings.SERVICE_NAME}


@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """La conexiÃ³n a la base propia del servicio responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "servicio": settings.SERVICE_NAME, "database": "ok"}


@app.get("/health/storage", tags=["health"])
def health_storage() -> dict[str, str]:
    """El bucket de evidencias (MinIO/S3) existe y responde al usuario de MS4.

    Si el almacenamiento falla, responde 503 con un mensaje genÃ©rico: nunca se
    filtran el endpoint, las claves ni el nombre del bucket (checklist 2.1).
    """
    try:
        cliente = crear_cliente_s3(settings)
        almacenamiento_ok = verificar_bucket(cliente, settings.S3_BUCKET)
    except Exception:  # noqa: BLE001  (falla de configuraciÃ³n o de red â†’ 503)
        almacenamiento_ok = False

    if not almacenamiento_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El almacenamiento de evidencias no estÃ¡ disponible",
        )
    return {"status": "ok", "servicio": settings.SERVICE_NAME, "storage": "ok"}

