"""Integridad referencial, índices y mapeos ORM de los cuatro servicios.

Semana 9 · "Revisar integridad referencial, índices y consultas ORM utilizadas
por los servicios". Detalle: docs/revision-integridad-referencial-orm.md.

Cada servicio se migra con SUS migraciones (alembic upgrade head) en una base
PostgreSQL descartable y se comprueba:

1. Los modelos ORM y las migraciones describen el mismo esquema
   (`alembic.autogenerate.compare_metadata` sin diferencias, salvo las
   excepciones justificadas de `DIFERENCIAS_ACEPTADAS`).
2. Toda tabla tiene clave primaria.
3. Toda clave foránea tiene un índice que empieza por sus columnas (borrar o
   actualizar el padre no recorre la tabla hija entera), salvo las listadas
   en `FK_SIN_INDICE_ACEPTADAS`. Una FK nueva sin índice hace fallar la prueba.
4. Cada FK declara su política ON DELETE de forma explícita y coincide con la
   del modelo ORM.
5. No hay FK entre bases: cada servicio solo referencia sus propias tablas.

Requiere `INTEGRIDAD_PG_ADMIN_URL`: un PostgreSQL LOCAL donde se puedan crear
bases (por ejemplo postgresql+psycopg://taller:taller@localhost:5432/postgres).
Crea y borra bases `verificar_integridad_<servicio>_<uuid>`; nunca toca otras.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

RAIZ_BACKEND = Path(__file__).resolve().parents[1]

SERVICIOS = {
    "ms1_auth": "MS1",
    "ms2_taller": "MS2",
    "ms3_presupuestos": "MS3",
    "ms4_evidencias": "MS4",
}

# Diferencias modelo ↔ migración que se aceptan a propósito (servicio -> índices).
DIFERENCIAS_ACEPTADAS: dict[str, set[str]] = {
    # Índices GIN de búsqueda sobre ms3_normalizar(nombre) (pg_trgm, 0006_ms3):
    # dependen de una función y una extensión que solo existen en PostgreSQL,
    # por eso viven solo en la migración y no en el modelo (que también se usa
    # con SQLite en las pruebas de integración).
    "ms3_presupuestos": {"ix_repuesto_nombre_trgm", "ix_proveedor_nombre_trgm",
                         "ix_proveedor_contacto_trgm"},
}

# FK sin índice propio aceptadas, con el motivo (tabla.columna).
FK_SIN_INDICE_ACEPTADAS: dict[str, dict[str, str]] = {
    "ms1_auth": {
        "usuario_rol.rol_id": "rol tiene 3 filas y nunca se borra (RESTRICT); propuesta de índice en la revisión",
        "usuario_rol.asignado_por_id": "SET NULL solo al borrar un usuario (no hay borrado físico en la API)",
        "historial_rol.rol_id": "rol tiene 3 filas y nunca se borra (RESTRICT)",
        "historial_rol.responsable_id": "SET NULL solo al borrar un usuario (no hay borrado físico en la API)",
    },
    "ms2_taller": {
        "historial_estado.estado_anterior": "catálogo fijo de 8 estados que nunca se borra (RESTRICT)",
        "historial_estado.estado_nuevo": "catálogo fijo de 8 estados que nunca se borra (RESTRICT)",
        "historial_validacion_cupo_ingreso.ingreso_id": "historial de auditoría; propuesta de índice en la revisión",
    },
}


@pytest.fixture(scope="module")
def admin() -> Iterator[Engine]:
    url = os.environ.get("INTEGRIDAD_PG_ADMIN_URL")
    if not url:
        pytest.skip("Defina INTEGRIDAD_PG_ADMIN_URL (PostgreSQL local descartable)")
    destino = make_url(url)
    assert destino.host in {"127.0.0.1", "localhost", "::1"}, "Solo un PostgreSQL local"
    motor = create_engine(url, isolation_level="AUTOCOMMIT")
    yield motor
    motor.dispose()


@pytest.fixture(scope="module", params=list(SERVICIOS))
def base_migrada(request, admin: Engine) -> Iterator[tuple[str, Engine]]:
    """Base nueva con las migraciones del servicio aplicadas hasta head."""
    servicio = request.param
    nombre = f"verificar_integridad_{servicio}_{uuid.uuid4().hex[:8]}"
    with admin.connect() as conexion:
        conexion.execute(text(f'create database "{nombre}"'))
    url = admin.url.set(database=nombre)
    prefijo = SERVICIOS[servicio]
    entorno = dict(os.environ)
    entorno[f"{prefijo}_DATABASE_URL"] = url.render_as_string(hide_password=False)
    entorno.setdefault(f"{prefijo}_JWT_SECRET_KEY", "clave-local-de-pruebas-de-integridad-1234567890")
    motor = create_engine(url)
    try:
        resultado = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", f"services/{servicio}/alembic.ini", "upgrade", "head"],
            cwd=RAIZ_BACKEND, env=entorno, capture_output=True, text=True, timeout=120,
        )
        assert resultado.returncode == 0, resultado.stderr[-2000:]
        yield servicio, motor
    finally:
        motor.dispose()
        with admin.connect() as conexion:
            conexion.execute(text(f'drop database if exists "{nombre}" with (force)'))


def _metadata(servicio: str):
    importlib.import_module(f"services.{servicio}.models")
    return importlib.import_module(f"services.{servicio}.db").Base.metadata


def _claves_foraneas(motor: Engine) -> list[dict]:
    consulta = text("""
        select c.conrelid::regclass::text as tabla,
               array(select a.attname from unnest(c.conkey) with ordinality k(n, i)
                     join pg_attribute a on a.attrelid = c.conrelid and a.attnum = k.n
                     order by k.i) as columnas,
               c.confrelid::regclass::text as referida,
               c.confdeltype as al_borrar,
               exists (select 1 from pg_index i
                       where i.indrelid = c.conrelid
                         and (i.indkey::int2[])[0:array_length(c.conkey, 1) - 1] = c.conkey) as indexada
        from pg_constraint c join pg_namespace n on n.oid = c.connamespace
        where c.contype = 'f' and n.nspname = 'public'
        order by 1, 2
    """)
    with motor.connect() as conexion:
        return [dict(fila._mapping) for fila in conexion.execute(consulta)]


def test_modelos_y_migraciones_describen_el_mismo_esquema(base_migrada) -> None:
    servicio, motor = base_migrada
    with motor.connect() as conexion:
        diferencias = compare_metadata(
            MigrationContext.configure(conexion, opts={"compare_type": True}), _metadata(servicio))
    aceptadas = DIFERENCIAS_ACEPTADAS.get(servicio, set())
    inesperadas = [d for d in diferencias
                   if not (d[0] == "remove_index" and d[1].name in aceptadas)]
    assert inesperadas == [], f"{servicio}: el modelo ORM y las migraciones no coinciden"


def test_toda_tabla_tiene_clave_primaria(base_migrada) -> None:
    _, motor = base_migrada
    with motor.connect() as conexion:
        sin_pk = conexion.execute(text("""
            select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where c.relkind = 'r' and n.nspname = 'public'
              and not exists (select 1 from pg_constraint p where p.conrelid = c.oid and p.contype = 'p')
        """)).scalars().all()
    assert sin_pk == []


def test_toda_clave_foranea_tiene_indice(base_migrada) -> None:
    servicio, motor = base_migrada
    sin_indice = {f"{fk['tabla']}.{','.join(fk['columnas'])}"
                  for fk in _claves_foraneas(motor) if not fk["indexada"]}
    assert sin_indice == set(FK_SIN_INDICE_ACEPTADAS.get(servicio, {})), (
        "FK sin índice: agregue el índice en una migración o documente la excepción")


_ON_DELETE = {"a": None, "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}


def test_politica_on_delete_explicita_e_igual_al_modelo(base_migrada) -> None:
    servicio, motor = base_migrada
    modelo = {
        (tabla.name, tuple(c.parent.name for c in fk.elements)): (fk.ondelete or "").upper() or None
        for tabla in _metadata(servicio).sorted_tables for fk in tabla.foreign_key_constraints
    }
    for fk in _claves_foraneas(motor):
        clave = (fk["tabla"], tuple(fk["columnas"]))
        base = _ON_DELETE[fk["al_borrar"]]
        assert base is not None, f"{clave}: ON DELETE sin declarar (NO ACTION implícito)"
        assert modelo.get(clave) == base, f"{clave}: modelo {modelo.get(clave)} ≠ base {base}"


def test_no_hay_claves_foraneas_entre_servicios(base_migrada) -> None:
    servicio, motor = base_migrada
    propias = {t.name for t in _metadata(servicio).sorted_tables}
    assert {fk["referida"] for fk in _claves_foraneas(motor)} <= propias
