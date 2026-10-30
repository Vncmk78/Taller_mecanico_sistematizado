"""Entorno de Alembic para MS2 (Vehículos y Órdenes de Trabajo).

Enlaza las migraciones con la metadata de los modelos ORM de MS2 y con el engine
de ESTE servicio (que ya trae su propia URL desde .env, prefijo MS2_). No se
duplican credenciales en alembic.ini.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, String, Table, inspect, text
from sqlalchemy.engine import Connection

# El engine y la Base propios de MS2. Importar el paquete de modelos registra
# todas las tablas del servicio en Base.metadata para que Alembic las vea.
from services.ms2_taller.db import Base, engine
from services.ms2_taller import models  # noqa: F401  (registra los modelos)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def preparar_tabla_versiones(conexion: Connection) -> None:
    """Conserva los IDs históricos de más de 32 caracteres sin truncarlos.

    Se ejecuta en la misma transacción que las migraciones y respeta el esquema
    de la conexión (también los esquemas aislados de pruebas). Solo amplía la
    columna técnica de Alembic; no cambia datos del dominio ni versiones guardadas.
    """
    if conexion.dialect.name != "postgresql":
        return
    versiones = Table(
        "alembic_version", MetaData(),
        Column("version_num", String(64), nullable=False),
        PrimaryKeyConstraint("version_num", name="alembic_version_pkc"),
    )
    versiones.create(conexion, checkfirst=True)
    columna = next(
        c for c in inspect(conexion).get_columns("alembic_version")
        if c["name"] == "version_num"
    )
    largo = getattr(columna["type"], "length", None)
    if largo is not None and largo < 64:
        conexion.execute(text(
            "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"
        ))


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
    """Ejecuta las migraciones conectándose a la base propia de MS2."""
    # Igual que MS3: permite migrar un esquema de pruebas con conexión inyectada.
    conexion_externa = config.attributes.get("connection")
    if conexion_externa is not None:
        context.configure(
            connection=conexion_externa, target_metadata=target_metadata, compare_type=True,
        )
        with context.begin_transaction():
            preparar_tabla_versiones(conexion_externa)
            context.run_migrations()
        return

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            preparar_tabla_versiones(connection)
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
