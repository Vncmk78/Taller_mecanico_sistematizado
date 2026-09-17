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
