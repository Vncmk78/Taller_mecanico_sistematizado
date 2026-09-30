"""Fixtures de las pruebas de persistencia ORM de MS3.

Las pruebas corren contra un PostgreSQL con las migraciones de MS3 aplicadas
(`alembic -c services/ms3_presupuestos/alembic.ini upgrade head`): los
triggers de versionado no existen en SQLite.

La URL se toma de MS3_ORM_TEST_DATABASE_URL; si no está definida se usa la base
local del docker-compose (puerto 5435). Si la base no responde o no está en la
última migración, las pruebas se OMITEN (skip) en vez de fallar.

Cada prueba corre en una transacción que se revierte al final: no dejan datos.
"""
from __future__ import annotations

import os

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

URL_POR_DEFECTO = "postgresql+psycopg://taller:taller@localhost:5435/taller_ms3"
RUTA_ALEMBIC = "services/ms3_presupuestos/alembic.ini"


@pytest.fixture(scope="session")
def engine() -> Engine:
    url = os.environ.get("MS3_ORM_TEST_DATABASE_URL", URL_POR_DEFECTO)
    eng = create_engine(url)
    head = ScriptDirectory.from_config(Config(RUTA_ALEMBIC)).get_current_head()
    try:
        with eng.connect() as conexion:
            version = conexion.execute(text("select version_num from alembic_version")).scalar()
    except (OperationalError, ProgrammingError) as exc:
        eng.dispose()
        pytest.skip(f"PostgreSQL de MS3 no disponible para pruebas ORM: {exc.orig}")
    if version != head:
        eng.dispose()
        pytest.skip(f"La base de MS3 está en {version}, se requiere {head} (alembic upgrade head)")
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Session:
    """Sesión ORM dentro de una transacción que SIEMPRE se revierte."""
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint",
                     expire_on_commit=False)
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()


# --------------------------------------------------------------------------- #
# Fixtures de datos mínimos (ver fabricas.py y datos_prueba.py)               #
# --------------------------------------------------------------------------- #
# Todas viven dentro de la transacción de `db`: se crean al pedirlas y
# desaparecen al terminar la prueba.

from services.ms3_presupuestos.models import (  # noqa: E402
    ParametroInventario,
    Presupuesto,
    Repuesto,
)
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo  # noqa: E402
from services.ms3_presupuestos.tests import fabricas  # noqa: E402


@pytest.fixture
def uow(db: Session) -> UnidadDeTrabajo:
    """Unidad de trabajo sobre la sesión de prueba."""
    return UnidadDeTrabajo(db)


@pytest.fixture
def catalogo(db: Session) -> dict[str, Repuesto]:
    """Catálogo mínimo: 2 proveedores, 4 repuestos e ingreso inicial de stock."""
    return fabricas.cargar_catalogo(db)


@pytest.fixture
def repuesto_bajo_umbral(catalogo: dict[str, Repuesto]) -> Repuesto:
    from services.ms3_presupuestos.datos_prueba import REPUESTO_BAJO_UMBRAL
    return catalogo[REPUESTO_BAJO_UMBRAL]


@pytest.fixture
def umbral_general(db: Session) -> ParametroInventario:
    """Un único umbral general vigente (= datos_prueba.UMBRAL_GENERAL)."""
    return fabricas.umbral_general_vigente(db)


@pytest.fixture
def presupuesto_borrador(db: Session) -> Presupuesto:
    return fabricas.nuevo_presupuesto(db, estado="borrador")


@pytest.fixture
def presupuesto_enviado(db: Session) -> Presupuesto:
    return fabricas.nuevo_presupuesto(db, estado="enviado")


@pytest.fixture
def presupuesto_aprobado(db: Session) -> Presupuesto:
    return fabricas.nuevo_presupuesto(db, estado="aprobado")


@pytest.fixture
def presupuesto_rechazado(db: Session) -> Presupuesto:
    return fabricas.nuevo_presupuesto(db, estado="rechazado")


@pytest.fixture
def presupuesto_ejemplo(db: Session, catalogo: dict[str, Repuesto]) -> Presupuesto:
    """El presupuesto de la semilla (pastillas + mano de obra = $68.990), enviado."""
    return fabricas.nuevo_presupuesto(db, estado="enviado",
                                      items=fabricas.items_de_ejemplo(catalogo))
