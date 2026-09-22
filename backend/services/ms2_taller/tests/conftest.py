"""Fixtures para las pruebas rápidas de migración de MS2.

Las pruebas se ejecutan contra la base **ya migrada** de MS2 (`alembic upgrade
head`). Cada prueba corre dentro de una transacción que se revierte al final, así
que no dejan datos y se pueden repetir sin limpiar nada.

La URL se toma de `MS2_DATABASE_URL` (misma variable que usa el servicio); si no
está definida, usa la base local por defecto del docker-compose (puerto 5434).
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

URL_POR_DEFECTO = "postgresql+psycopg://taller:taller@localhost:5434/taller_ms2"


@pytest.fixture(scope="session")
def engine() -> Engine:
    url = os.environ.get("MS2_DATABASE_URL", URL_POR_DEFECTO)
    eng = create_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture
def conn(engine: Engine) -> Connection:
    """Conexión con transacción que SIEMPRE se revierte al terminar la prueba."""
    with engine.connect() as c:
        trans = c.begin()
        try:
            yield c
        finally:
            trans.rollback()
