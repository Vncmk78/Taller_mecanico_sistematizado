"""Capa de persistencia del microservicio MS4.

Dominio: metadatos de fotografías y videos por orden: contexto, autor, fecha y visibilidad (los archivos viven en MinIO/S3, no en PostgreSQL).

Este servicio se conecta ÚNICAMENTE a su propia base (MS4). No existen
claves foráneas físicas hacia las bases de los otros servicios: esas relaciones
son lógicas y se resuelven por contrato de API (Sistematización final §8).
"""
from __future__ import annotations

from shared.db import (
    crear_base,
    crear_dependencia_sesion,
    crear_engine,
    crear_session_factory,
)

from services.ms4_evidencias.config import settings

# Base declarativa propia: todos los modelos de MS4 heredan de aquí y solo
# estos entran en las migraciones de MS4.
Base = crear_base()

engine = crear_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

SessionLocal = crear_session_factory(engine)

# Dependencia que se inyecta en los endpoints: `db: Session = Depends(get_db)`.
get_db = crear_dependencia_sesion(SessionLocal)
