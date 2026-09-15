"""Conexión a la base de datos y estructura de persistencia (SQLAlchemy 2).

Ticket [DB] Semana 1: "Configurar conexión de base de datos y estructura de
persistencia mediante ORM". Aquí se crea el engine hacia PostgreSQL y la
fábrica de sesiones que usarán todos los servicios del backend.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Engine: punto único de conexión al pool de PostgreSQL.
# pool_pre_ping evita usar conexiones muertas (reinicios de la BD, timeouts).
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    future=True,
)

# Fábrica de sesiones. expire_on_commit=False deja los objetos utilizables
# después de un commit (cómodo al devolver datos en los endpoints).
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: entrega una sesión y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
