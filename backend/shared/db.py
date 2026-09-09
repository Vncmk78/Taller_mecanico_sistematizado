"""Fábrica de la capa de persistencia (SQLAlchemy 2.0).

Este módulo NO crea ningún engine por sí solo: entrega funciones que cada
microservicio usa para construir su propia base declarativa, su engine y su
fábrica de sesiones. Así los cuatro servicios comparten convenciones y código,
pero cada uno queda atado únicamente a su propia base de datos.
"""
from __future__ import annotations

from collections.abc import Callable, Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Nombres predecibles para índices y restricciones. Sin esto, Alembic genera
# nombres automáticos distintos en cada máquina y las migraciones dejan de ser
# reproducibles entre los integrantes del equipo.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def crear_base(schema: str | None = None) -> type[DeclarativeBase]:
    """Devuelve una base declarativa nueva e independiente para un servicio.

    Cada microservicio necesita su PROPIO MetaData: si compartieran uno, las
    tablas de los cuatro dominios terminarían en la misma migración y se
    perdería el aislamiento que exige §8.
    """
    metadata_servicio = MetaData(naming_convention=NAMING_CONVENTION, schema=schema)

    class Base(DeclarativeBase):
        metadata = metadata_servicio

    return Base


def crear_engine(
    url: str,
    *,
    echo: bool = False,
    pool_size: int = 5,
    max_overflow: int = 10,
) -> Engine:
    """Crea el engine hacia la base del servicio.

    pool_pre_ping descarta conexiones muertas antes de usarlas (reinicios de
    PostgreSQL, cortes de red, timeouts del contenedor).
    """
    if not url:
        raise RuntimeError(
            "DATABASE_URL vacía. Copia .env.example a .env y define la cadena "
            "de conexión de este servicio."
        )
    return create_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        future=True,
    )


def crear_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Fábrica de sesiones del servicio.

    autocommit/autoflush en False: la transacción se abre y se cierra de forma
    explícita, que es lo que necesitan las reglas de capacidad y de stock
    (§4.6 y §4.7) para controlar concurrencia.
    """
    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def crear_dependencia_sesion(
    session_factory: sessionmaker[Session],
) -> Callable[[], Generator[Session, None, None]]:
    """Devuelve la dependencia `get_db` que inyecta FastAPI en cada endpoint.

    Hace rollback si el endpoint lanza una excepción y cierra siempre la sesión,
    para no dejar conexiones ocupadas en el pool.
    """

    def get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return get_db
