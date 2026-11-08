"""PostgreSQL real: solicitudes concurrentes, índice A y migración aislada.

Usa REGISTRO_ORDEN_MS2_TEST_URL y la fixture de esquemas descartables. No
consulta ni migra bases compartidas. Los datos revisados son fixtures de C.
"""
import threading
import time
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from services.ms2_taller.models import EventoOutbox, HistorialEstado, IngresoVehiculo, OrdenTrabajo, SolicitudNuevaAtencion
from services.ms2_taller.models.estado_orden import CANCELADO
from services.ms2_taller.services.nuevas_atenciones import (
    NuevaAtencionConflictoError, PersistenciaNuevaAtencionError, solicitar_nueva_atencion,
)
from services.ms2_taller.services.ordenes import (
    crear_orden, registrar_devolucion_fisica, _consulta_vehiculo_para_actualizacion,
)
from shared.auth import NombreRol, PrincipalAutenticado
from test_registro_orden_postgresql import motor_pg, _sesion, _fijar_cupo, _vehiculos  # noqa: F401

CLIENTE = PrincipalAutenticado(10, frozenset({NombreRol.CLIENTE}))


def _preparar(motor):
    _fijar_cupo(motor, 10)
    (vehiculo_id,) = _vehiculos(motor, 1)
    with _sesion(motor) as db:
        orden = crear_orden(db, vehiculo_id, 99)
        orden.estado_codigo = CANCELADO
        db.commit()
        return orden.orden_id, vehiculo_id, orden.ingreso_id


def _solicitar(db, orden_id, descripcion="Revisar los frenos"):
    return solicitar_nueva_atencion(db, orden_id=orden_id, principal=CLIENTE, descripcion=descripcion)


@pytest.mark.parametrize("identicas", [True, False])
def test_solicitudes_simultaneas_crean_una_y_clasifican_reintentos(motor_pg, identicas):
    orden_id, _, ingreso_id = _preparar(motor_pg)
    barrera = threading.Barrier(6)
    def solicitar(n):
        with _sesion(motor_pg) as db:
            barrera.wait(timeout=10)
            try:
                solicitud, creada = _solicitar(db, orden_id, "Revisar" if identicas else f"Revisar {n}")
                return solicitud.solicitud_id, solicitud.solicitada_en, creada
            except NuevaAtencionConflictoError as exc:
                return exc
    with ThreadPoolExecutor(max_workers=6) as pool:
        resultados = list(pool.map(solicitar, range(6)))
    exitos = [r for r in resultados if isinstance(r, tuple)]
    assert sum(r[2] for r in exitos) == 1
    assert len(exitos) == (6 if identicas else 1)
    assert len({r[:2] for r in exitos}) == 1
    assert exitos[0][1].tzinfo is not None
    assert sum(isinstance(r, NuevaAtencionConflictoError) for r in resultados) == (0 if identicas else 5)
    with _sesion(motor_pg) as db:
        assert db.scalar(select(func.count()).select_from(SolicitudNuevaAtencion)) == 1
        for modelo in (OrdenTrabajo, IngresoVehiculo, HistorialEstado, EventoOutbox):
            assert db.scalar(select(func.count()).select_from(modelo)) == 1
        assert db.get(IngresoVehiculo, ingreso_id).salida_en is None


def test_indice_a_rechaza_escritura_directa_y_permite_nueva_tras_rechazo(motor_pg):
    orden_id, vehiculo_id, _ = _preparar(motor_pg)
    with _sesion(motor_pg) as db:
        primera, _ = _solicitar(db, orden_id)
        original_id = primera.solicitud_id
        with pytest.raises(IntegrityError) as error:
            db.add(SolicitudNuevaAtencion(orden_cancelada_id=orden_id, vehiculo_id=vehiculo_id,
                                         cliente_usuario_id=10, descripcion="Otra"))
            db.commit()
        assert error.value.orig.diag.constraint_name == "uq_nueva_atencion_vigente_por_orden"
        db.rollback()
        primera = db.get(SolicitudNuevaAtencion, original_id)
        primera.situacion = "rechazada"
        primera.respuesta = "Se requiere otra descripción"
        primera.revisor_id = 99
        primera.revisada_en = func.now()
        db.commit()
        nueva, creada = _solicitar(db, orden_id)
        assert creada and nueva.solicitud_id != original_id
        assert db.get(SolicitudNuevaAtencion, original_id).situacion == "rechazada"
        assert db.scalar(select(func.count()).select_from(SolicitudNuevaAtencion)) == 2


def test_indice_a_con_aceptada_y_orden_generada_sigue_bloqueando(motor_pg):
    orden_id, vehiculo_id, _ = _preparar(motor_pg)
    with _sesion(motor_pg) as db:
        primera, _ = _solicitar(db, orden_id)
        nueva_orden = crear_orden(db, vehiculo_id, 99)
        primera.situacion = "aceptada"
        primera.respuesta = "Se acepta"
        primera.revisor_id = 99
        primera.revisada_en = func.now()
        primera.orden_generada_id = nueva_orden.orden_id
        db.commit()
        with pytest.raises(NuevaAtencionConflictoError):
            _solicitar(db, orden_id)
        with pytest.raises(IntegrityError) as error:
            db.add(SolicitudNuevaAtencion(orden_cancelada_id=orden_id, vehiculo_id=vehiculo_id,
                                         cliente_usuario_id=10, descripcion="Otra"))
            db.commit()
        assert error.value.orig.diag.constraint_name == "uq_nueva_atencion_vigente_por_orden"
        db.rollback()


def test_fallo_commit_revierte_solicitud_y_libera_lock_para_reintentar(motor_pg):
    orden_id, _, _ = _preparar(motor_pg)
    with _sesion(motor_pg) as db:
        def fallar():
            raise SQLAlchemyError("fallo de commit de prueba")
        db.commit = fallar
        with pytest.raises(PersistenciaNuevaAtencionError):
            _solicitar(db, orden_id)
    with _sesion(motor_pg) as db:
        assert db.scalar(select(func.count()).select_from(SolicitudNuevaAtencion)) == 0
        solicitud, creada = _solicitar(db, orden_id)
        assert creada and solicitud.orden_cancelada_id == orden_id


def test_solicitud_concurrente_con_devolucion_no_forma_ciclo_de_bloqueos(motor_pg):
    """Fuerza que el solicitante espere un lock de una devolución en curso.

    Si solicitara bloqueando orden antes que vehículo, el INSERT esperaría
    la FK del vehículo y la devolución esperaría la orden: deadlock real.
    """
    orden_id, vehiculo_id, ingreso_id = _preparar(motor_pg)
    pids = Queue()
    def solicitar():
        with _sesion(motor_pg) as db:
            pids.put(db.scalar(text("select pg_backend_pid()")))
            return _solicitar(db, orden_id)[0].solicitud_id
    with _sesion(motor_pg) as salida, ThreadPoolExecutor(max_workers=1) as pool:
        salida.scalar(_consulta_vehiculo_para_actualizacion(vehiculo_id))
        futuro = pool.submit(solicitar)
        pid = pids.get(timeout=10)
        limite = time.monotonic() + 5
        esperando = False
        with motor_pg.connect().execution_options(isolation_level="AUTOCOMMIT") as observador:
            while time.monotonic() < limite:
                esperando = observador.scalar(text(
                    "select wait_event_type = 'Lock' from pg_stat_activity where pid = :pid"
                ), {"pid": pid})
                if esperando:
                    break
                time.sleep(.01)
        if not esperando:
            # Liberar siempre antes de esperar al worker si falla el diagnóstico.
            salida.rollback()
        assert esperando, "La petición debe haber llegado a esperar el bloqueo real"
        registrar_devolucion_fisica(salida, orden_id=orden_id, administrador_id=99)
        solicitud_id = futuro.result(timeout=10)
    with _sesion(motor_pg) as db:
        assert db.get(IngresoVehiculo, ingreso_id).salida_en is not None
        assert db.get(SolicitudNuevaAtencion, solicitud_id).orden_cancelada_id == orden_id


def test_migracion_crea_tabla_sin_modificar_datos_existentes_y_es_reversible(motor_pg):
    orden_id, _, ingreso_id = _preparar(motor_pg)
    def migrar(destino, bajar=False):
        with motor_pg.begin() as c:
            cfg = Config(); cfg.set_main_option("script_location", "services/ms2_taller/alembic")
            cfg.attributes["connection"] = c
            (command.downgrade if bajar else command.upgrade)(cfg, destino)
    def datos():
        with motor_pg.connect() as c:
            return (c.execute(text("select * from orden_trabajo order by orden_id")).all(),
                    c.execute(text("select * from ingreso_vehiculo order by ingreso_id")).all())
    antes = datos()
    migrar("0013_orden_activa_ms2", bajar=True)
    assert "solicitud_nueva_atencion" not in inspect(motor_pg).get_table_names()
    migrar("head")
    assert datos() == antes
    assert "solicitud_nueva_atencion" in inspect(motor_pg).get_table_names()
    indices = {i["name"] for i in inspect(motor_pg).get_indexes("solicitud_nueva_atencion")}
    assert {"uq_nueva_atencion_vigente_por_orden", "ix_nueva_atencion_cliente_fecha"} <= indices
    with _sesion(motor_pg) as db:
        assert _solicitar(db, orden_id)[1]
        assert db.get(IngresoVehiculo, ingreso_id).salida_en is None


@pytest.mark.parametrize("valores", [
    {"descripcion": ""}, {"descripcion": "x" * 2001}, {"cliente_usuario_id": 0},
    {"situacion": "completada"}, {"situacion": "pendiente", "respuesta": "respuesta anticipada"},
    {"situacion": "aceptada"}, {"orden_generada_id": "antecedente"},
])
def test_restricciones_rechazan_datos_incoherentes_en_base(motor_pg, valores):
    orden_id, vehiculo_id, _ = _preparar(motor_pg)
    datos = {"orden_cancelada_id": orden_id, "vehiculo_id": vehiculo_id,
             "cliente_usuario_id": 10, "descripcion": "Revisar"}
    datos.update(valores)
    if datos.get("orden_generada_id") == "antecedente":
        datos["orden_generada_id"] = orden_id
    with _sesion(motor_pg) as db:
        db.add(SolicitudNuevaAtencion(**datos))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.scalar(select(func.count()).select_from(SolicitudNuevaAtencion)) == 0
