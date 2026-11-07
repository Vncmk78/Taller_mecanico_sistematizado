"""Registro de órdenes con PostgreSQL real: concurrencia del cupo y rollback.

Se omite salvo que `REGISTRO_ORDEN_MS2_TEST_URL` apunte a una base PostgreSQL
local y descartable (`postgresql+psycopg://.../verificar_*`). Cada prueba crea
un esquema propio, aplica las migraciones reales de MS2 y lo elimina al final.

Comprueba que el bloqueo de la configuración del cupo serializa las altas
simultáneas, que los rechazos quedan auditados con los datos leídos bajo ese
bloqueo, que un ingreso abierto se reutiliza aun con altas simultáneas del
mismo vehículo y que una falla deshace ingreso, orden, historial y evento.
No agrega ninguna regla sobre varias órdenes activas por vehículo.
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
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker

import services.ms2_taller.services.ordenes as servicio_ordenes
from services.ms2_taller.models import (
    Cliente,
    ConfiguracionCupoIngresos,
    EventoOutbox,
    HistorialEstado,
    IngresoVehiculo,
    OrdenTrabajo,
    Vehiculo,
)
from services.ms2_taller.models.configuracion_cupo_ingresos import (
    HistorialValidacionCupoIngreso,
)
from services.ms2_taller.services.cupo_ingresos import (
    CupoDiarioExcedidoError,
    CupoDiarioNoConfiguradoError,
)
from services.ms2_taller.services.ordenes import PersistenciaOrdenError, crear_orden

_VARIABLE = "REGISTRO_ORDEN_MS2_TEST_URL"
ADMIN = 99


@pytest.fixture
def motor_pg() -> Generator[Engine, None, None]:
    url = os.environ.get(_VARIABLE)
    if not url:
        pytest.skip(f"Se requiere {_VARIABLE} con un PostgreSQL local descartable")
    destino = make_url(url)
    assert destino.drivername == "postgresql+psycopg"
    assert destino.host in {"127.0.0.1", "localhost", "::1"}
    assert destino.database.startswith("verificar_"), "No usar bases compartidas"

    esquema = f"prueba_registro_{uuid.uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as conexion:
        conexion.execute(text(f'create schema "{esquema}"'))
        conexion.execute(text(f'set local search_path to "{esquema}"'))
        config = Config()
        config.set_main_option("script_location", "services/ms2_taller/alembic")
        config.attributes["connection"] = conexion
        command.upgrade(config, "head")

    # El esquema va como parámetro de conexión: un SET dentro de la primera
    # transacción se perdería con un rollback.
    motor = create_engine(
        url, pool_size=12, connect_args={"options": f"-c search_path={esquema}"}
    )
    try:
        yield motor
    finally:
        motor.dispose()
        with admin.begin() as conexion:
            conexion.execute(text(f'drop schema "{esquema}" cascade'))
        admin.dispose()


def _sesion(motor: Engine):
    return sessionmaker(bind=motor, expire_on_commit=False)()


def _fijar_cupo(motor: Engine, maximo: int | None) -> None:
    with _sesion(motor) as db:
        db.execute(
            update(ConfiguracionCupoIngresos)
            .where(ConfiguracionCupoIngresos.configuracion_id == 1)
            .values(max_ingresos_diarios=maximo, actualizado_por_id=ADMIN)
        )
        db.commit()


def _vehiculos(motor: Engine, cantidad: int) -> list[int]:
    with _sesion(motor) as db:
        cliente = Cliente(usuario_id=10)
        db.add(cliente)
        db.flush()
        vehiculos = [
            Vehiculo(cliente_id=cliente.cliente_id, patente=f"PG{i:04d}", marca="Kia", modelo="Rio")
            for i in range(cantidad)
        ]
        db.add_all(vehiculos)
        db.commit()
        return [v.vehiculo_id for v in vehiculos]


def _contar(motor: Engine, modelo) -> int:
    with _sesion(motor) as db:
        return db.scalar(select(func.count()).select_from(modelo))


def _crear_en_paralelo(motor: Engine, vehiculo_ids: list[int]) -> list[object]:
    barrera = threading.Barrier(len(vehiculo_ids))

    def crear(vehiculo_id: int):
        with _sesion(motor) as db:
            barrera.wait(timeout=10)
            try:
                return crear_orden(db, vehiculo_id, ADMIN)
            except Exception as exc:  # se clasifican en la prueba
                return exc

    with ThreadPoolExecutor(max_workers=len(vehiculo_ids)) as ejecutor:
        return list(ejecutor.map(crear, vehiculo_ids))


@pytest.mark.parametrize("maximo", [1, 3])
def test_altas_simultaneas_nunca_superan_el_cupo_y_auditan_cada_rechazo(
    motor_pg: Engine, maximo: int
) -> None:
    _fijar_cupo(motor_pg, maximo)
    ids = _vehiculos(motor_pg, 6)

    resultados = _crear_en_paralelo(motor_pg, ids)

    exitos = [r for r in resultados if isinstance(r, OrdenTrabajo)]
    rechazos = [r for r in resultados if isinstance(r, CupoDiarioExcedidoError)]
    assert len(exitos) == maximo
    assert len(rechazos) == 6 - maximo
    assert _contar(motor_pg, IngresoVehiculo) == maximo
    assert _contar(motor_pg, OrdenTrabajo) == maximo
    assert _contar(motor_pg, HistorialEstado) == maximo
    assert _contar(motor_pg, EventoOutbox) == maximo
    with _sesion(motor_pg) as db:
        validaciones = db.scalars(select(HistorialValidacionCupoIngreso)).all()
    aceptadas = [v for v in validaciones if v.aceptada]
    rechazadas = [v for v in validaciones if not v.aceptada]
    assert len(aceptadas) == maximo and all(v.ingreso_id is not None for v in aceptadas)
    assert len(rechazadas) == 6 - maximo
    # Cada rechazo conserva lo leído bajo el bloqueo: el cupo ya estaba lleno.
    assert {(v.resultado, v.ingresos_registrados, v.max_ingresos_diarios, v.ingreso_id)
            for v in rechazadas} == {("cupo_excedido", maximo, maximo, None)}


def test_altas_simultaneas_del_mismo_vehiculo_comparten_un_ingreso(motor_pg: Engine) -> None:
    """Comportamiento vigente: se reutiliza el ingreso abierto (sin regla nueva)."""

    _fijar_cupo(motor_pg, 5)
    (vehiculo_id,) = _vehiculos(motor_pg, 1)

    resultados = _crear_en_paralelo(motor_pg, [vehiculo_id] * 4)

    assert all(isinstance(r, OrdenTrabajo) for r in resultados)
    assert len({r.ingreso_id for r in resultados}) == 1
    assert _contar(motor_pg, IngresoVehiculo) == 1
    assert _contar(motor_pg, OrdenTrabajo) == 4
    with _sesion(motor_pg) as db:
        assert db.scalar(
            select(func.count()).select_from(HistorialValidacionCupoIngreso)
        ) == 1  # solo el ingreso nuevo valida cupo


def test_rechazo_sin_cupo_configurado_audita_y_no_deja_registros(motor_pg: Engine) -> None:
    _fijar_cupo(motor_pg, None)
    (vehiculo_id,) = _vehiculos(motor_pg, 1)

    with _sesion(motor_pg) as db, pytest.raises(CupoDiarioNoConfiguradoError):
        crear_orden(db, vehiculo_id, ADMIN)

    assert _contar(motor_pg, IngresoVehiculo) == 0
    assert _contar(motor_pg, OrdenTrabajo) == 0
    with _sesion(motor_pg) as db:
        rechazo = db.scalar(select(HistorialValidacionCupoIngreso))
    assert (rechazo.aceptada, rechazo.resultado, rechazo.max_ingresos_diarios) == (
        False, "cupo_no_configurado", None,
    )
    assert rechazo.vehiculo_id == vehiculo_id and rechazo.administrador_id == ADMIN


def test_falla_despues_del_ingreso_deshace_todo_y_libera_los_bloqueos(
    motor_pg: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fijar_cupo(motor_pg, 1)
    primero, segundo = _vehiculos(motor_pg, 2)
    registrar_real = servicio_ordenes.registrar_historial_estado

    def fallar(*_args, **_kwargs):
        raise servicio_ordenes.SQLAlchemyError("fallo simulado en el historial")

    monkeypatch.setattr(servicio_ordenes, "registrar_historial_estado", fallar)
    with _sesion(motor_pg) as db, pytest.raises(PersistenciaOrdenError):
        crear_orden(db, primero, ADMIN)
    monkeypatch.setattr(servicio_ordenes, "registrar_historial_estado", registrar_real)

    for modelo in (IngresoVehiculo, OrdenTrabajo, HistorialEstado, EventoOutbox,
                   HistorialValidacionCupoIngreso):
        assert _contar(motor_pg, modelo) == 0, modelo.__name__
    # El cupo no quedó consumido ni bloqueado: otra alta usa el único lugar.
    with _sesion(motor_pg) as db:
        orden = crear_orden(db, segundo, ADMIN)
    assert orden.estado_codigo == 1
    assert _contar(motor_pg, IngresoVehiculo) == 1
