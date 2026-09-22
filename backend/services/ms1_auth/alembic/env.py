"""Entorno de Alembic para MS1 (Autenticación y Usuarios).

Enlaza las migraciones con la metadata de los modelos ORM de MS1 y con el engine
de ESTE servicio (que ya trae su propia URL desde .env, prefijo MS1_). No se
duplican credenciales en alembic.ini.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context

# El engine y la Base propios de MS1. Importar el paquete de modelos registra
# todas las tablas del servicio en Base.metadata para que Alembic las vea.
from services.ms1_auth.db import Base, engine
from services.ms1_auth import models  # noqa: F401  (registra los modelos)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse a la base (modo --sql)."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta las migraciones conectándose a la base propia de MS1."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
