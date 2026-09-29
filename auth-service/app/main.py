"""Punto de entrada del microservicio de Autenticación y Usuarios (MS1)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infrastructure.api.routes_auth import router as auth_router
from app.infrastructure.config import settings
from app.infrastructure.db.models import Base
from app.infrastructure.db.session import engine

app = FastAPI(
    title="MS1 - Autenticación y Usuarios",
    description="Microservicio de cuentas, roles y sesiones del Taller Mecánico Sistematizado.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.on_event("startup")
def on_startup() -> None:
    # Para Sprint 1 creamos las tablas directamente; en Sprint 2 se migra a Alembic.
    Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "auth-service"}
