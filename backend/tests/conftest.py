"""Fixtures aisladas para probar MS1 sin una instancia PostgreSQL externa."""

from __future__ import annotations

import os
from collections.abc import Generator

os.environ.setdefault(
    "MS1_JWT_SECRET_KEY",
    "clave-secreta-exclusiva-para-pruebas-de-ms1-123456",
)
os.environ.setdefault(
    "MS1_DATABASE_URL",
    "sqlite+pysqlite:////tmp/sgtm_ms1_config_only.db",
)
os.environ.setdefault(
    "MS2_JWT_SECRET_KEY",
    "clave-secreta-exclusiva-para-pruebas-de-ms2-123456",
)
os.environ.setdefault(
    "MS2_DATABASE_URL",
    "sqlite+pysqlite:////tmp/sgtm_ms2_config_only.db",
)
# Las pruebas HTTP no deben arrancar el publicador que usa la base/servicio
# externo configurado en el .env del desarrollador.
os.environ["MS2_EVENT_WORKER_ENABLED"] = "false"
os.environ.setdefault(
    "MS3_JWT_SECRET_KEY",
    "clave-secreta-exclusiva-para-pruebas-de-ms3-123456",
)
os.environ.setdefault(
    "MS3_DATABASE_URL",
    "sqlite+pysqlite:////tmp/sgtm_ms3_config_only.db",
)
os.environ.setdefault(
    "MS4_JWT_SECRET_KEY",
    "clave-secreta-exclusiva-para-pruebas-de-ms4-123456",
)
os.environ.setdefault(
    "MS4_DATABASE_URL",
    "sqlite+pysqlite:////tmp/sgtm_ms4_config_only.db",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms1_auth.db import Base, get_db
from services.ms1_auth.main import app
from services.ms1_auth.models import Rol
from shared.auth import NombreRol


@pytest.fixture
def mecanicos_validos():
    """MS1 simulado para suites de estados/capacidad; la validación HTTP tiene suite propia."""
    from types import SimpleNamespace
    from services.ms2_taller.main import app as ms2
    from services.ms2_taller.integracion_ms1 import obtener_verificador_mecanicos

    ms2.dependency_overrides[obtener_verificador_mecanicos] = lambda: SimpleNamespace(
        verificar=lambda _mecanico_id, _token: None,
    )
    yield
    ms2.dependency_overrides.pop(obtener_verificador_mecanicos, None)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    sesion = fabrica()
    sesion.add_all([Rol(nombre=rol.value) for rol in NombreRol])
    sesion.commit()
    try:
        yield sesion
    finally:
        sesion.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def api(db: Session) -> Generator[TestClient, None, None]:
    def reemplazar_db():
        yield db

    app.dependency_overrides[get_db] = reemplazar_db
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


# ── Almacenamiento S3 exclusivo para las pruebas reales de MS4 ──────────────
# Ver tests/almacenamiento_s3_desechable.py: nunca se usa el bucket configurado
# de MS4; cada prueba crea sus buckets y al final elimina solo esos.


@pytest.fixture
def s3_prueba():
    from almacenamiento_s3_desechable import MOTIVO_SIN_CONFIGURAR, config_desde_entorno

    configuracion = config_desde_entorno()
    if configuracion is None:
        pytest.skip(MOTIVO_SIN_CONFIGURAR)
    return configuracion


@pytest.fixture
def almacenamiento(s3_prueba):
    from almacenamiento_s3_desechable import AlmacenamientoDesechable

    propio = AlmacenamientoDesechable(s3_prueba.cliente())
    yield propio
    # Si la limpieza falla, la prueba termina con error (no se oculta).
    propio.limpiar()
