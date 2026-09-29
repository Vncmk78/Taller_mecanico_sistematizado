"""Modelos ORM del microservicio MS4.

Se importan aquí TODOS los modelos del servicio para que `Base.metadata` (y por
lo tanto Alembic) los vea al generar y ejecutar las migraciones.

Semana 3: Evidencia (metadatos de fotos y videos) con sus enums de dominio.
Referencia: lámina 04-mer-erd, recuadro "BD MS4", y docs/modelo-evidencias.md.
"""
from __future__ import annotations

from services.ms4_evidencias.db import Base
from services.ms4_evidencias.models.evidencia import (
    ContextoEvidencia,
    EstadoEvidencia,
    Evidencia,
    TipoArchivo,
)

__all__ = [
    "Base",
    "Evidencia",
    "ContextoEvidencia",
    "TipoArchivo",
    "EstadoEvidencia",
]
