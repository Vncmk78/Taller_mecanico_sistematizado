"""Salida física atómica, devolución cancelada e idempotencia HTTP."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from services.ms2_taller.models import (
    EventoOutbox, HistorialEstado, HistorialValidacionCupoIngreso,
    IngresoVehiculo, OrdenTrabajo,
)
from services.ms2_taller.models.estado_orden import CANCELADO, ENTREGADO, LISTO
from services.ms2_taller.services.ordenes import crear_orden, registrar_entrega_fisica
from shared.auth import NombreRol
from test_ordenes_api import (  # noqa: F401: fixtures SQLite/HTTP existentes
    api_ordenes, db_ordenes, _crear_orden, _headers_para,
)

ADMIN = _headers_para(99, NombreRol.ADMINISTRADOR)


def _post(api, orden_id, headers=ADMIN, **kwargs):
    return api.post(f"/ordenes/{orden_id}/devolucion", headers=headers, **kwargs)


def test_devolucion_cierra_ingreso_sin_transicion_y_es_consultable(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    antes = api_ordenes.get(f"/ordenes/{orden.orden_id}", headers=ADMIN).json()
    assert antes["devuelto_en"] is antes["devuelto_por_id"] is None
    respuesta = _post(api_ordenes, orden.orden_id, json={})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado_codigo"] == CANCELADO
    assert datos["devuelto_por_id"] == 99
    assert datetime.fromisoformat(datos["devuelto_en"]).tzinfo is not None
    assert "historial_id" not in datos
    db_ordenes.expire_all()
    actual = db_ordenes.get(OrdenTrabajo, orden.orden_id)
    ingreso = db_ordenes.get(IngresoVehiculo, orden.ingreso_id)
    assert ingreso.salida_en == actual.devuelto_en
    for modelo in (HistorialEstado, EventoOutbox, HistorialValidacionCupoIngreso):
        assert db_ordenes.scalar(select(func.count()).select_from(modelo)) == 0
    for ruta in (f"/ordenes/{orden.orden_id}", "/ordenes",
                 f"/ordenes/vehiculo/{orden.vehiculo_id}/historial"):
        resultado = api_ordenes.get(ruta, headers=_headers_para(10, NombreRol.CLIENTE))
        assert resultado.status_code == 200
        contenido = resultado.json()
        fila = contenido[0] if isinstance(contenido, list) else contenido.get("items", [contenido])[0]
        assert fila["devuelto_en"] == datos["devuelto_en"]
        assert fila["devuelto_por_id"] == 99


def test_reintento_por_otro_admin_preserva_fecha_actor_y_estancia_nueva(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    primera = _post(api_ordenes, orden.orden_id, json={})
    nueva = crear_orden(db_ordenes, orden.vehiculo_id, 100)
    segunda = _post(api_ordenes, orden.orden_id,
                    headers=_headers_para(100, NombreRol.CLIENTE, NombreRol.ADMINISTRADOR), json={})
    assert primera.status_code == segunda.status_code == 200
    assert primera.json() == segunda.json()
    assert nueva.ingreso_id != orden.ingreso_id
    assert db_ordenes.get(IngresoVehiculo, nueva.ingreso_id).salida_en is None


def test_cancelada_compartida_no_sale_hasta_entregar_activa(api_ordenes, db_ordenes):
    cancelada = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    activa = crear_orden(db_ordenes, cancelada.vehiculo_id, 99)
    assert activa.ingreso_id == cancelada.ingreso_id
    respuesta = _post(api_ordenes, cancelada.orden_id, json={})
    assert respuesta.status_code == 409
    assert f"n° {activa.orden_id}" in respuesta.json()["detail"]
    db_ordenes.expire_all()
    assert db_ordenes.get(IngresoVehiculo, activa.ingreso_id).salida_en is None
    assert db_ordenes.get(OrdenTrabajo, cancelada.orden_id).devuelto_en is None
    activa.estado_codigo = LISTO
    db_ordenes.commit()
    entrega = api_ordenes.post(f"/ordenes/{activa.orden_id}/entrega", headers=ADMIN)
    assert entrega.status_code == 200
    db_ordenes.expire_all()
    ingreso = db_ordenes.get(IngresoVehiculo, activa.ingreso_id)
    assert ingreso.salida_en == db_ordenes.get(OrdenTrabajo, activa.orden_id).entregado_en
    assert _post(api_ordenes, cancelada.orden_id, json={}).status_code == 409
    assert db_ordenes.get(OrdenTrabajo, cancelada.orden_id).devuelto_en is None


@pytest.mark.parametrize("estado", range(1, 8))
def test_devolucion_rechaza_orden_no_cancelada(api_ordenes, db_ordenes, estado):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=estado)
    assert _post(api_ordenes, orden.orden_id, json={}).status_code == 409
    db_ordenes.expire_all()
    assert db_ordenes.get(IngresoVehiculo, orden.ingreso_id).salida_en is None
    assert db_ordenes.get(OrdenTrabajo, orden.orden_id).devuelto_en is None


@pytest.mark.parametrize("rol", [NombreRol.CLIENTE, NombreRol.MECANICO])
def test_devolucion_exige_admin_aunque_sea_propietario(api_ordenes, db_ordenes, rol):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    assert _post(api_ordenes, orden.orden_id, headers=_headers_para(10, rol), json={}).status_code == 403
    assert orden.devuelto_en is None


def test_devolucion_sin_sesion_o_inexistente(api_ordenes):
    assert _post(api_ordenes, 999, headers={}, json={}).status_code == 401
    assert _post(api_ordenes, 999, json={}).status_code == 404


@pytest.mark.parametrize("body", [None, {"devuelto_por_id": 100},
    {"devuelto_en": "2026-11-08T12:00:00Z"}, {"estado_codigo": 7}, []])
def test_devolucion_body_obligatorio_y_sin_campos_controlables(api_ordenes, db_ordenes, body):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    kwargs = {} if body is None else {"json": body}
    assert _post(api_ordenes, orden.orden_id, **kwargs).status_code == 422
    assert orden.devuelto_en is None


@pytest.mark.parametrize("identificador", [0, -1, "abc"])
def test_devolucion_id_invalido(api_ordenes, identificador):
    assert _post(api_ordenes, identificador, json={}).status_code == 422


@pytest.mark.parametrize("operacion", ["entrega", "devolucion"])
@pytest.mark.parametrize("punto", ["flush", "commit"])
def test_fallo_revierte_salida_auditoria_estado_historial_y_outbox(
    api_ordenes, db_ordenes, monkeypatch, operacion, punto,
):
    estado = LISTO if operacion == "entrega" else CANCELADO
    orden = _crear_orden(db_ordenes, 10, estado_codigo=estado)
    orden_id, ingreso_id = orden.orden_id, orden.ingreso_id
    original = getattr(db_ordenes, punto)

    def fallar(*args, **kwargs):
        # Solo falla una escritura, no el autoflush de las lecturas/bloqueos.
        if punto == "commit" or db_ordenes.dirty or db_ordenes.new:
            raise SQLAlchemyError("fallo de escritura de prueba")
        return original(*args, **kwargs)

    with monkeypatch.context() as parche:
        parche.setattr(db_ordenes, punto, fallar)
        respuesta = api_ordenes.post(f"/ordenes/{orden_id}/{operacion}", headers=ADMIN, json={})
    assert respuesta.status_code == 500
    db_ordenes.expire_all()
    actual = db_ordenes.get(OrdenTrabajo, orden_id)
    assert actual.estado_codigo == estado
    assert actual.devuelto_en is actual.devuelto_por_id is None
    assert actual.entregado_en is actual.entregado_por_id is None
    assert db_ordenes.get(IngresoVehiculo, ingreso_id).salida_en is None
    assert db_ordenes.scalar(select(func.count()).select_from(HistorialEstado)) == 0
    assert db_ordenes.scalar(select(func.count()).select_from(EventoOutbox)) == 0


def test_entrega_cierra_ingreso_y_reintento_no_cambia_salida(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=LISTO)
    primera = api_ordenes.post(f"/ordenes/{orden.orden_id}/entrega", headers=ADMIN)
    salida = db_ordenes.get(IngresoVehiculo, orden.ingreso_id).salida_en
    segunda = api_ordenes.post(f"/ordenes/{orden.orden_id}/entrega",
                              headers=_headers_para(100, NombreRol.ADMINISTRADOR))
    assert primera.status_code == segunda.status_code == 200
    assert primera.json() == segunda.json()
    db_ordenes.expire_all()
    assert db_ordenes.get(IngresoVehiculo, orden.ingreso_id).salida_en == salida
    assert salida == db_ordenes.get(OrdenTrabajo, orden.orden_id).entregado_en
    nueva = crear_orden(db_ordenes, orden.vehiculo_id, 99)
    assert nueva.ingreso_id != orden.ingreso_id


def test_reintento_entrega_historica_no_inventa_salida(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=LISTO)
    registrar_entrega_fisica(db_ordenes, orden_id=orden.orden_id, administrador_id=99)
    ingreso = db_ordenes.get(IngresoVehiculo, orden.ingreso_id)
    ingreso.salida_en = None  # simula el dato anterior a esta entrega
    db_ordenes.commit()
    respuesta = api_ordenes.post(f"/ordenes/{orden.orden_id}/entrega", headers=ADMIN)
    assert respuesta.status_code == 200
    db_ordenes.expire_all()
    assert db_ordenes.get(IngresoVehiculo, orden.ingreso_id).salida_en is None
    assert db_ordenes.get(OrdenTrabajo, orden.orden_id).estado_codigo == ENTREGADO


def test_devolucion_historica_sin_salida_requiere_revision_sin_reparacion(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    orden.devuelto_en = datetime.now(timezone.utc)
    orden.devuelto_por_id = 100
    db_ordenes.commit()
    antes = api_ordenes.get(f"/ordenes/{orden.orden_id}", headers=ADMIN).json()
    respuesta = _post(api_ordenes, orden.orden_id, json={})
    assert respuesta.status_code == 409
    assert "histórica está incompleta" in respuesta.json()["detail"]
    despues = api_ordenes.get(f"/ordenes/{orden.orden_id}", headers=ADMIN).json()
    assert despues == antes
    assert db_ordenes.get(IngresoVehiculo, orden.ingreso_id).salida_en is None


def test_entrega_con_ingreso_ya_cerrado_no_duplica_salida(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=LISTO)
    ingreso = db_ordenes.get(IngresoVehiculo, orden.ingreso_id)
    ingreso.salida_en = datetime.now(timezone.utc)
    db_ordenes.commit()
    fecha = ingreso.salida_en.replace(tzinfo=None)
    respuesta = api_ordenes.post(f"/ordenes/{orden.orden_id}/entrega", headers=ADMIN)
    assert respuesta.status_code == 409
    db_ordenes.expire_all()
    assert db_ordenes.get(IngresoVehiculo, orden.ingreso_id).salida_en == fecha
    assert db_ordenes.get(OrdenTrabajo, orden.orden_id).estado_codigo == LISTO
    assert db_ordenes.scalar(select(func.count()).select_from(HistorialEstado)) == 0
