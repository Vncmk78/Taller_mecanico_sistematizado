"""Salidas con PostgreSQL real: reintentos y cruces con el alta de órdenes.

Reutiliza la fixture que crea un esquema propio en una base verificar_* local;
nunca usa las tablas de la demostración. Sin URL explícita se omite.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from services.ms2_taller.models import EventoOutbox, HistorialEstado, IngresoVehiculo, OrdenTrabajo
from services.ms2_taller.models.estado_orden import CANCELADO, ENTREGADO, LISTO
from services.ms2_taller.services.ordenes import (
    SalidaVehiculoNoPermitidaError, PersistenciaOrdenError,
    _consulta_vehiculo_para_actualizacion, crear_orden,
    registrar_devolucion_fisica, registrar_entrega_fisica,
    registrar_orden_sin_confirmar,
)
from test_registro_orden_postgresql import (  # noqa: F401
    motor_pg, _sesion, _fijar_cupo, _vehiculos,
)


def _preparar(motor, estado):
    _fijar_cupo(motor, 10)
    (vehiculo_id,) = _vehiculos(motor, 1)
    with _sesion(motor) as db:
        orden = crear_orden(db, vehiculo_id, 99)
        orden.estado_codigo = estado
        db.commit()
        return orden.orden_id, vehiculo_id, orden.ingreso_id


def _salir(db, operacion, orden_id, admin):
    if operacion == "entrega":
        return registrar_entrega_fisica(db, orden_id=orden_id, administrador_id=admin)[0]
    return registrar_devolucion_fisica(db, orden_id=orden_id, administrador_id=admin)


@pytest.mark.parametrize("operacion,estado", [("entrega", LISTO), ("devolucion", CANCELADO)])
def test_reintentos_concurrentes_conservan_una_fecha_y_un_responsable(motor_pg, operacion, estado):
    orden_id, _, ingreso_id = _preparar(motor_pg, estado)
    barrera = threading.Barrier(4)

    def salir(admin):
        with _sesion(motor_pg) as db:
            # Incluso una sesión con una copia anterior debe refrescar tras el lock.
            copia_anterior = db.get(OrdenTrabajo, orden_id)
            barrera.wait(timeout=10)
            orden = _salir(db, operacion, orden_id, admin)
            assert orden is copia_anterior
            return ((orden.entregado_en, orden.entregado_por_id) if operacion == "entrega"
                    else (orden.devuelto_en, orden.devuelto_por_id))

    with ThreadPoolExecutor(max_workers=4) as pool:
        resultados = list(pool.map(salir, range(99, 103)))
    assert len(set(resultados)) == 1
    fecha, admin = resultados[0]
    assert fecha.tzinfo is not None and admin in range(99, 103)
    with _sesion(motor_pg) as db:
        assert db.get(IngresoVehiculo, ingreso_id).salida_en == fecha
        assert db.get(OrdenTrabajo, orden_id).estado_codigo == (ENTREGADO if operacion == "entrega" else CANCELADO)
        for modelo in (HistorialEstado, EventoOutbox):
            assert db.scalar(select(func.count()).select_from(modelo)) == (2 if operacion == "entrega" else 1)


@pytest.mark.parametrize("operacion,estado", [("entrega", LISTO), ("devolucion", CANCELADO)])
def test_salida_que_toma_lock_primero_obliga_a_crear_otro_ingreso(motor_pg, operacion, estado):
    orden_id, vehiculo_id, ingreso_id = _preparar(motor_pg, estado)
    salida_escrita, alta_iniciada = threading.Event(), threading.Event()

    def salir():
        with _sesion(motor_pg) as db:
            commit_original = db.commit

            def confirmar():
                salida_escrita.set()  # el flush de salida ya ocurrió, lock vigente
                assert alta_iniciada.wait(timeout=10)
                commit_original()

            db.commit = confirmar
            _salir(db, operacion, orden_id, 99)

    def crear():
        assert salida_escrita.wait(timeout=10)
        with _sesion(motor_pg) as db:
            alta_iniciada.set()
            return crear_orden(db, vehiculo_id, 100).ingreso_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        salida = pool.submit(salir)
        nueva = pool.submit(crear)
        salida.result(timeout=20)
        nuevo_ingreso = nueva.result(timeout=20)
    assert nuevo_ingreso != ingreso_id
    with _sesion(motor_pg) as db:
        assert db.get(IngresoVehiculo, ingreso_id).salida_en is not None
        assert db.get(IngresoVehiculo, nuevo_ingreso).salida_en is None


def test_alta_que_toma_lock_primero_impide_devolver_el_ingreso_compartido(motor_pg):
    orden_id, vehiculo_id, ingreso_id = _preparar(motor_pg, CANCELADO)
    alta_bloqueada, salida_iniciada = threading.Event(), threading.Event()

    def crear():
        with _sesion(motor_pg) as db:
            db.scalar(_consulta_vehiculo_para_actualizacion(vehiculo_id))
            nueva = registrar_orden_sin_confirmar(db, vehiculo_id, 100)
            alta_bloqueada.set()
            assert salida_iniciada.wait(timeout=10)
            db.commit()
            return nueva.ingreso_id

    def devolver():
        assert alta_bloqueada.wait(timeout=10)
        with _sesion(motor_pg) as db:
            salida_iniciada.set()
            with pytest.raises(SalidaVehiculoNoPermitidaError, match="sigue activa"):
                registrar_devolucion_fisica(db, orden_id=orden_id, administrador_id=99)

    with ThreadPoolExecutor(max_workers=2) as pool:
        alta = pool.submit(crear)
        salida = pool.submit(devolver)
        assert alta.result(timeout=20) == ingreso_id
        salida.result(timeout=20)
    with _sesion(motor_pg) as db:
        assert db.get(IngresoVehiculo, ingreso_id).salida_en is None
        assert db.get(OrdenTrabajo, orden_id).devuelto_en is None


@pytest.mark.parametrize("operacion,estado", [("entrega", LISTO), ("devolucion", CANCELADO)])
def test_fallo_commit_revierte_la_salida_y_libera_bloqueos(motor_pg, operacion, estado):
    orden_id, _, ingreso_id = _preparar(motor_pg, estado)
    with _sesion(motor_pg) as db:
        def fallar():
            raise SQLAlchemyError("fallo de commit de prueba")
        db.commit = fallar
        with pytest.raises(PersistenciaOrdenError):
            _salir(db, operacion, orden_id, 99)
    with _sesion(motor_pg) as db:
        assert db.get(IngresoVehiculo, ingreso_id).salida_en is None
        orden = db.get(OrdenTrabajo, orden_id)
        assert orden.estado_codigo == estado
        assert orden.entregado_en is orden.devuelto_en is None
        assert db.scalar(select(func.count()).select_from(HistorialEstado)) == 1
        assert db.scalar(select(func.count()).select_from(EventoOutbox)) == 1
        # Otra conexión puede completar la operación tras el rollback.
        _salir(db, operacion, orden_id, 100)
    with _sesion(motor_pg) as db:
        assert db.get(IngresoVehiculo, ingreso_id).salida_en is not None
