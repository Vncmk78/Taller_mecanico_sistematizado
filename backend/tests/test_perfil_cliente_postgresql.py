"""Concurrencia real de la preparación del perfil Cliente en PostgreSQL.

Se omite salvo que `PERFIL_CLIENTE_MS2_TEST_URL` apunte a una base PostgreSQL
local y descartable (`postgresql+psycopg://.../verificar_*`). Cada prueba crea
un esquema propio, aplica las migraciones reales de MS2 (con la restricción
`uq_cliente_usuario_id`) y lo elimina al terminar.

SQLite no permite dos escrituras simultáneas reales; aquí se comprueba que
preparaciones concurrentes del mismo usuario terminan en un único perfil y que
la que pierde la carrera recupera el perfil ganador en vez de fallar.
"""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker

import services.ms2_taller.services.clientes as servicio_clientes
from services.ms2_taller.models import Cliente

_VARIABLE = "PERFIL_CLIENTE_MS2_TEST_URL"


@pytest.fixture
def motor_pg() -> Generator[Engine, None, None]:
    url = os.environ.get(_VARIABLE)
    if not url:
        pytest.skip(f"Se requiere {_VARIABLE} con un PostgreSQL local descartable")
    destino = make_url(url)
    assert destino.drivername == "postgresql+psycopg"
    assert destino.host in {"127.0.0.1", "localhost", "::1"}
    assert destino.database.startswith("verificar_"), "No usar bases compartidas"

    esquema = f"prueba_perfil_{uuid.uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as conexion:
        conexion.execute(text(f'create schema "{esquema}"'))
        conexion.execute(text(f'set local search_path to "{esquema}"'))
        config = Config()
        config.set_main_option("script_location", "services/ms2_taller/alembic")
        config.attributes["connection"] = conexion
        command.upgrade(config, "head")

    # El esquema se fija como parámetro de la conexión: un `SET` dentro de la
    # primera transacción se perdería con el rollback de la carrera perdida.
    motor = create_engine(
        url, pool_size=10, connect_args={"options": f"-c search_path={esquema}"}
    )

    try:
        yield motor
    finally:
        motor.dispose()
        with admin.begin() as conexion:
            conexion.execute(text(f'drop schema "{esquema}" cascade'))
        admin.dispose()


def _contar(motor: Engine, usuario_id: int) -> int:
    with sessionmaker(bind=motor)() as sesion:
        return sesion.scalar(
            select(func.count()).select_from(Cliente).where(Cliente.usuario_id == usuario_id)
        )


def _preparar(motor: Engine, usuario_id: int, barrera: threading.Barrier | None = None):
    with sessionmaker(bind=motor, expire_on_commit=False)() as sesion:
        if barrera is not None:
            barrera.wait(timeout=10)
        cliente, creado = servicio_clientes.preparar_perfil_cliente(sesion, usuario_id)
        return cliente.cliente_id, creado


def test_preparaciones_simultaneas_dejan_un_unico_perfil(motor_pg: Engine) -> None:
    hilos = 8
    barrera = threading.Barrier(hilos)
    with ThreadPoolExecutor(max_workers=hilos) as ejecutor:
        resultados = list(
            ejecutor.map(lambda _: _preparar(motor_pg, 501, barrera), range(hilos))
        )

    assert _contar(motor_pg, 501) == 1
    assert len({cliente_id for cliente_id, _ in resultados}) == 1
    assert any(creado for _, creado in resultados)


def test_insercion_perdedora_usa_la_restriccion_unica_y_recupera_el_ganador(
    motor_pg: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fuerza que dos transacciones lleguen a insertar el mismo `usuario_id`.

    Cada hilo ve "sin perfil" en las tres búsquedas previas a la inserción y se
    sincroniza justo antes de insertar. PostgreSQL rechaza la segunda inserción
    con `uq_cliente_usuario_id`; `asegurar_cliente` la traduce y relee el
    perfil confirmado por el otro hilo.
    """

    buscar_real = servicio_clientes.buscar_cliente_por_usuario_id
    barrera = threading.Barrier(2)
    local = threading.local()

    def buscar_con_carrera(db, usuario_id):
        local.llamadas = getattr(local, "llamadas", 0) + 1
        if local.llamadas < 3:
            return None
        if local.llamadas == 3:  # búsqueda interna de `crear_cliente`
            barrera.wait(timeout=10)
            return None
        return buscar_real(db, usuario_id)

    monkeypatch.setattr(
        servicio_clientes, "buscar_cliente_por_usuario_id", buscar_con_carrera
    )
    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = list(ejecutor.map(lambda _: _preparar(motor_pg, 777), range(2)))

    assert _contar(motor_pg, 777) == 1
    assert resultados[0][0] == resultados[1][0]
