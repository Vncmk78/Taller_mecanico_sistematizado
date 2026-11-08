"""Entrega C con PostgreSQL real: concurrencia, cupo, salida y rollback."""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from services.ms2_taller.models import EventoOutbox, HistorialEstado, IngresoVehiculo, OrdenTrabajo, SolicitudNuevaAtencion
from services.ms2_taller.models.configuracion_cupo_ingresos import HistorialValidacionCupoIngreso
from services.ms2_taller.services.nuevas_atenciones import (
    NuevaAtencionConflictoError, PersistenciaNuevaAtencionError,
    revisar_nueva_atencion, generar_orden_nueva_atencion, solicitar_nueva_atencion,
)
from services.ms2_taller.services.ordenes import (
    crear_orden, registrar_devolucion_fisica, SalidaVehiculoNoPermitidaError, VehiculoConOrdenActivaError,
)
from shared.auth import NombreRol, PrincipalAutenticado
from test_nuevas_atenciones_postgresql import _preparar
from test_registro_orden_postgresql import motor_pg, _sesion, _fijar_cupo, _vehiculos  # noqa: F401

ADMIN = PrincipalAutenticado(99, frozenset({NombreRol.ADMINISTRADOR}))
CLIENTE = PrincipalAutenticado(10, frozenset({NombreRol.CLIENTE}))


def _solicitud(motor, aceptar=True):
    oid, vid, iid = _preparar(motor)
    with _sesion(motor) as db:
        s, _ = solicitar_nueva_atencion(db, orden_id=oid, principal=CLIENTE, descripcion="Revisar")
        if aceptar:
            revisar_nueva_atencion(db, solicitud_id=s.solicitud_id, principal=ADMIN, decision="aceptada", respuesta="Sí")
        return s.solicitud_id, oid, vid, iid


@pytest.mark.parametrize("identicas", [True, False])
def test_revisiones_simultaneas_son_inmutables_y_producen_un_evento(motor_pg, identicas):
    sid, _, _, _ = _solicitud(motor_pg, aceptar=False)
    barrera = threading.Barrier(6)
    def revisar(n):
        with _sesion(motor_pg) as db:
            barrera.wait(timeout=10)
            try:
                actor = PrincipalAutenticado(99+n, ADMIN.roles)
                s = revisar_nueva_atencion(db, solicitud_id=sid, principal=actor, decision="aceptada", respuesta="Sí" if identicas else f"Sí {n}")
                return s.revisor_id, s.revisada_en, s.respuesta
            except NuevaAtencionConflictoError as exc:
                return exc
    with ThreadPoolExecutor(max_workers=6) as pool:
        resultados = list(pool.map(revisar, range(6)))
    exitos = [r for r in resultados if isinstance(r, tuple)]
    assert len(exitos) == (6 if identicas else 1) and len(set(exitos)) == 1
    with _sesion(motor_pg) as db:
        assert len(db.scalars(select(EventoOutbox).where(EventoOutbox.tipo == "nueva_atencion.revisada")).all()) == 1


def test_generaciones_simultaneas_crean_una_orden_y_un_vinculo(motor_pg):
    sid, _, _, _ = _solicitud(motor_pg)
    barrera = threading.Barrier(6)
    def generar(n):
        with _sesion(motor_pg) as db:
            barrera.wait(timeout=10)
            s, orden, creada = generar_orden_nueva_atencion(db, solicitud_id=sid, principal=PrincipalAutenticado(99+n, ADMIN.roles))
            return s.orden_generada_id, orden.orden_id, orden.creado_por_id, creada
    with ThreadPoolExecutor(max_workers=6) as pool:
        resultados = list(pool.map(generar, range(6)))
    assert sum(r[3] for r in resultados) == 1
    assert len({r[:3] for r in resultados}) == 1
    with _sesion(motor_pg) as db:
        for modelo, cantidad in [(OrdenTrabajo, 2), (IngresoVehiculo, 1), (HistorialEstado, 2), (EventoOutbox, 3)]:
            assert db.scalar(select(func.count()).select_from(modelo)) == cantidad


def test_generacion_compite_con_alta_normal_y_solo_una_puede_ganar(motor_pg):
    sid, _, vid, _ = _solicitud(motor_pg)
    barrera = threading.Barrier(2)
    def generar():
        with _sesion(motor_pg) as db:
            barrera.wait(timeout=10)
            try:
                return generar_orden_nueva_atencion(db, solicitud_id=sid, principal=ADMIN)[1].orden_id
            except NuevaAtencionConflictoError:
                return None
    def normal():
        with _sesion(motor_pg) as db:
            barrera.wait(timeout=10)
            try:
                return crear_orden(db, vid, 100).orden_id
            except VehiculoConOrdenActivaError:
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(generar), pool.submit(normal)
        generada, directa = a.result(timeout=15), b.result(timeout=15)
    assert (generada is None) != (directa is None)
    with _sesion(motor_pg) as db:
        assert db.get(SolicitudNuevaAtencion, sid).orden_generada_id == generada
        assert db.scalar(select(func.count()).select_from(OrdenTrabajo)) == 2


def test_generacion_y_devolucion_no_dejan_una_orden_activa_en_ingreso_cerrado(motor_pg):
    sid, oid, _, iid = _solicitud(motor_pg)
    barrera = threading.Barrier(2)
    def generar():
        with _sesion(motor_pg) as db:
            barrera.wait(timeout=10)
            return generar_orden_nueva_atencion(db, solicitud_id=sid, principal=ADMIN)[1].orden_id
    def devolver():
        with _sesion(motor_pg) as db:
            barrera.wait(timeout=10)
            try:
                registrar_devolucion_fisica(db, orden_id=oid, administrador_id=99)
                return True
            except SalidaVehiculoNoPermitidaError:
                return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(generar), pool.submit(devolver)
        nueva_id, devuelta = a.result(timeout=15), b.result(timeout=15)
    with _sesion(motor_pg) as db:
        nueva = db.get(OrdenTrabajo, nueva_id)
        assert db.get(IngresoVehiculo, nueva.ingreso_id).salida_en is None
        assert (nueva.ingreso_id != iid) == devuelta
        assert (db.get(IngresoVehiculo, iid).salida_en is not None) == devuelta


def test_fallo_commit_revierte_toda_la_generacion_y_libera_locks(motor_pg):
    sid, oid, _, _ = _solicitud(motor_pg)
    with _sesion(motor_pg) as db:
        registrar_devolucion_fisica(db, orden_id=oid, administrador_id=99)
    with _sesion(motor_pg) as db:
        db.commit = lambda: (_ for _ in ()).throw(SQLAlchemyError("fallo commit de prueba"))
        with pytest.raises(PersistenciaNuevaAtencionError):
            generar_orden_nueva_atencion(db, solicitud_id=sid, principal=ADMIN)
    with _sesion(motor_pg) as db:
        assert db.get(SolicitudNuevaAtencion, sid).orden_generada_id is None
        for modelo, cantidad in [(OrdenTrabajo, 1), (IngresoVehiculo, 1), (HistorialEstado, 1), (EventoOutbox, 2), (HistorialValidacionCupoIngreso, 1)]:
            assert db.scalar(select(func.count()).select_from(modelo)) == cantidad
        assert generar_orden_nueva_atencion(db, solicitud_id=sid, principal=ADMIN)[2]


def test_generaciones_de_distintos_vehiculos_no_superan_cupo_y_auditan_rechazo(motor_pg):
    _fijar_cupo(motor_pg, 10)
    vehiculos = _vehiculos(motor_pg, 2)
    solicitudes = []
    for vid in vehiculos:
        with _sesion(motor_pg) as db:
            orden = crear_orden(db, vid, 99); orden.estado_codigo = 8; db.commit()
            registrar_devolucion_fisica(db, orden_id=orden.orden_id, administrador_id=99)
            s, _ = solicitar_nueva_atencion(db, orden_id=orden.orden_id, principal=CLIENTE, descripcion="Revisar")
            revisar_nueva_atencion(db, solicitud_id=s.solicitud_id, principal=ADMIN, decision="aceptada", respuesta="Sí")
            solicitudes.append(s.solicitud_id)
    _fijar_cupo(motor_pg, 3)
    barrera = threading.Barrier(2)
    def generar(sid):
        with _sesion(motor_pg) as db:
            barrera.wait(timeout=10)
            try:
                return generar_orden_nueva_atencion(db, solicitud_id=sid, principal=ADMIN)[2]
            except NuevaAtencionConflictoError:
                return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(generar, solicitudes)) == [False, True]
    with _sesion(motor_pg) as db:
        assert db.scalar(select(func.count()).select_from(IngresoVehiculo)) == 3
        rechazos = db.scalars(select(HistorialValidacionCupoIngreso).where(HistorialValidacionCupoIngreso.aceptada.is_(False))).all()
        assert len(rechazos) == 1 and rechazos[0].ingresos_registrados == 3 and rechazos[0].max_ingresos_diarios == 3
        assert sum(db.get(SolicitudNuevaAtencion, sid).orden_generada_id is not None for sid in solicitudes) == 1
