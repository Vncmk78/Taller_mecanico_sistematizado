"""Entorno de Alembic para MS4 (Evidencia Multimedia).

Enlaza las migraciones con la metadata de los modelos ORM de MS4 y con el engine
de ESTE servicio (que ya trae su propia URL desde .env, prefijo MS4_). No se
duplican credenciales en alembic.ini.

Los tests inyectan una conexión ya creada (normalmente SQLite en memoria) en
`config.attributes["connection"]`: si está presente, se usa ESA conexión en
lugar del engine, sin tocar el PostgreSQL de desarrollo.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context

# El engine y la Base propios de MS4. Importar el paquete de modelos registra
# todas las tablas del servicio en Base.metadata para que Alembic las vea.
from services.ms4_evidencias.db import Base, engine
from services.ms4_evidencias import models  # noqa: F401  (registra los modelos)

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
    """Ejecuta las migraciones conectándose a la base propia de MS4.

    Si el que ejecuta el contexto inyectó una conexión lista (tests), se usa esa
    en lugar del engine; de lo contrario se abre una conexión del engine normal.
    """
    conexion_externa = config.attributes.get("connection")
    if conexion_externa is not None:
        context.configure(
            connection=conexion_externa,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

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
