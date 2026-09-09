"""Modelos ORM del microservicio MS3.

Vacío por ahora. Los modelos se agregan en la tarea de Semana 1/2
"Crear modelos ORM iniciales" y deben importarse aquí para que Alembic los vea
al generar las migraciones.

Referencia: lámina 04-mer-erd, recuadro "BD MS3".
"""
from __future__ import annotations

from services.ms3_presupuestos.db import Base

__all__ = ["Base"]
