"""Pruebas de estructura y migración del microservicio MS4.

Verifican que el esqueleto del servicio quedó coherente:

- `/health` responde 200 (el proceso levanta).
- `/health/storage` con el cliente S3 simulado (monkeypatch): 200 si el bucket
  existe y 503 con mensaje genérico (sin filtro de endpoint ni de claves) si no.
- Alembic tiene UN solo head y es `0001_ms4`.
- `upgrade head` sobre SQLite en memoria crea la tabla `evidencia` y
  `compare_metadata` contra `Base.metadata` sale vacío (la migración y el modelo
  coinciden).
- `downgrade base` deja la base sin la tabla `evidencia`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

from services.ms4_evidencias import models  # noqa: F401  (registra modelos)
from services.ms4_evidencias.db import Base
from services.ms4_evidencias.main import app

RUTA_ALEMBIC = "services/ms4_evidencias/alembic.ini"


def _configura_alembic(conexion) -> Config:
    cfg = Config(RUTA_ALEMBIC)
    cfg.attributes["connection"] = conexion
    return cfg


def _motor_sqlite() -> object:
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


# --------------------------------------------------------------------------- #
# 1) Healthchecks                                                             #
# --------------------------------------------------------------------------- #

def test_health_responde_200() -> None:
    with TestClient(app) as cliente:
        respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"


def test_health_storage_200_si_el_bucket_responde(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.ms4_evidencias.main.crear_cliente_s3",
        lambda settings: object(),
    )
    monkeypatch.setattr(
        "services.ms4_evidencias.main.verificar_bucket",
        lambda cliente, bucket: True,
    )
    with TestClient(app) as cliente:
        respuesta = cliente.get("/health/storage")
    assert respuesta.status_code == 200
    assert respuesta.json()["storage"] == "ok"


def test_health_storage_503_sin_detalles_si_el_bucket_falla(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.ms4_evidencias.main.crear_cliente_s3",
        lambda settings: object(),
    )
    monkeypatch.setattr(
        "services.ms4_evidencias.main.verificar_bucket",
        lambda cliente, bucket: False,
    )
    with TestClient(app) as cliente:
        respuesta = cliente.get("/health/storage")
    assert respuesta.status_code == 503
    detalle = respuesta.json()["detail"]
    # Mensaje genérico: no se filtran endpoint, claves ni nombre del bucket.
    assert detalle == "El almacenamiento de evidencias no está disponible"


def test_health_storage_503_si_crear_cliente_falla(monkeypatch) -> None:
    def _cliente_falla(settings):
        raise RuntimeError("sin credenciales")

    monkeypatch.setattr(
        "services.ms4_evidencias.main.crear_cliente_s3",
        _cliente_falla,
    )
    with TestClient(app) as cliente:
        respuesta = cliente.get("/health/storage")
    assert respuesta.status_code == 503


# --------------------------------------------------------------------------- #
# 2) Migración                                                                #
# --------------------------------------------------------------------------- #

def test_alembic_tiene_un_solo_head_y_es_0001_ms4() -> None:
    cfg = Config(RUTA_ALEMBIC)
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["0001_ms4"]


def test_upgrade_head_crea_esquema_igual_al_modelo() -> None:
    motor = _motor_sqlite()
    with motor.connect() as conexion:
        cfg = _configura_alembic(conexion)

        command.upgrade(cfg, "head")

        tablas = inspect(conexion).get_table_names()
        assert "evidencia" in tablas

        contexto = MigrationContext.configure(conexion)
        assert compare_metadata(contexto, Base.metadata) == []

        command.downgrade(cfg, "base")

        assert "evidencia" not in inspect(conexion).get_table_names()
    motor.dispose()
