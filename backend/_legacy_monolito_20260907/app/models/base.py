"""Base declarativa de los modelos ORM.

Se fija una convención de nombres para índices y restricciones para que las
migraciones de Alembic generen nombres estables y predecibles en todo el equipo.
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos del sistema."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
