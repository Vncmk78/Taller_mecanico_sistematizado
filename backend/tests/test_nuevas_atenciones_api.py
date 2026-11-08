"""Solicitud de nueva atención: contrato, propiedad, reintentos y consultas."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from services.ms2_taller.models import (
    ConfiguracionCupoIngresos, EventoOutbox, HistorialEstado, HistorialValidacionCupoIngreso,
    IngresoVehiculo, OrdenTrabajo, SolicitudNuevaAtencion,
)
from services.ms2_taller.models.estado_orden import CANCELADO
from services.ms2_taller.services.ordenes import crear_orden, registrar_devolucion_fisica
from shared.auth import NombreRol
from test_ordenes_api import api_ordenes, db_ordenes, _crear_orden, _headers_para  # noqa: F401

BASE = "/ordenes/nuevas-atenciones"
CLIENTE = _headers_para(10, NombreRol.CLIENTE)
ADMIN = _headers_para(99, NombreRol.ADMINISTRADOR)
CAMPOS = {"solicitud_id", "orden_cancelada_id", "vehiculo_id", "cliente_usuario_id",
          "descripcion", "solicitada_en", "situacion", "respuesta", "revisor_id",
          "revisada_en", "orden_generada_id"}


def _solicitar(api, orden, descripcion="Revisar los frenos", headers=CLIENTE):
    return api.post(f"/ordenes/{orden.orden_id}/nueva-atencion", headers=headers,
                    json={"descripcion": descripcion})


def _revisada(db, solicitud_id, situacion, orden_generada_id=None):
    # Fixture de consulta de datos revisados: el endpoint de revisión es Entrega C.
    solicitud = db.get(SolicitudNuevaAtencion, solicitud_id)
    solicitud.situacion = situacion
    solicitud.respuesta = "Respuesta administrativa de prueba"
    solicitud.revisor_id = 99
    solicitud.revisada_en = datetime.now(timezone.utc)
    solicitud.orden_generada_id = orden_generada_id
    db.commit()


def test_crea_pendiente_desde_identidad_y_fecha_servidor_sin_efectos_laterales(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    modelos = (OrdenTrabajo, IngresoVehiculo, HistorialEstado, HistorialValidacionCupoIngreso)
    antes = [db_ordenes.scalar(select(func.count()).select_from(m)) for m in modelos]
    # Solicitar no depende de tener cupo configurado.
    db_ordenes.get(ConfiguracionCupoIngresos, 1).max_ingresos_diarios = None
    db_ordenes.commit()
    respuesta = _solicitar(api_ordenes, orden, "  Revisar los frenos  ")
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert set(datos) == CAMPOS
    assert datos["orden_cancelada_id"] == orden.orden_id
    assert datos["vehiculo_id"] == orden.vehiculo_id
    assert datos["cliente_usuario_id"] == 10
    assert datos["descripcion"] == "Revisar los frenos"
    assert datos["situacion"] == "pendiente"
    assert all(datos[c] is None for c in ("respuesta", "revisor_id", "revisada_en", "orden_generada_id"))
    assert datetime.fromisoformat(datos["solicitada_en"]).tzinfo is not None
    assert antes == [db_ordenes.scalar(select(func.count()).select_from(m)) for m in modelos]
    evento = db_ordenes.scalar(select(EventoOutbox).where(EventoOutbox.tipo == "nueva_atencion.solicitada"))
    assert evento.payload["solicitud_id"] == datos["solicitud_id"]
    assert evento.payload["cliente_usuario_id"] == 10
    assert db_ordenes.scalar(select(func.count()).select_from(EventoOutbox).where(EventoOutbox.tipo == "orden.estado_cambiado")) == 0
    db_ordenes.expire_all()
    assert db_ordenes.get(OrdenTrabajo, orden.orden_id).estado_codigo == CANCELADO
    assert db_ordenes.get(IngresoVehiculo, orden.ingreso_id).salida_en is None


@pytest.mark.parametrize("devuelta", [False, True])
def test_solicitar_permitido_antes_y_despues_de_devolver(api_ordenes, db_ordenes, devuelta):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    if devuelta:
        registrar_devolucion_fisica(db_ordenes, orden_id=orden.orden_id, administrador_id=99)
    assert _solicitar(api_ordenes, orden).status_code == 201


def test_solicitud_no_prohibe_otra_atencion_activa_del_vehiculo(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    crear_orden(db_ordenes, orden.vehiculo_id, 99)
    assert _solicitar(api_ordenes, orden).status_code == 201


def test_reintento_normalizado_devuelve_misma_pendiente_y_fecha(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    primera = _solicitar(api_ordenes, orden)
    segunda = _solicitar(api_ordenes, orden, "  Revisar los frenos\n")
    assert primera.status_code == 201 and segunda.status_code == 200
    assert primera.json() == segunda.json()
    assert db_ordenes.scalar(select(func.count()).select_from(SolicitudNuevaAtencion)) == 1
    assert _solicitar(api_ordenes, orden, "Otra descripción").status_code == 409


@pytest.mark.parametrize("con_orden", [False, True])
def test_aceptada_bloquea_otra_solicitud_incluso_si_genero_orden(api_ordenes, db_ordenes, con_orden):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    primera = _solicitar(api_ordenes, orden).json()
    nueva = crear_orden(db_ordenes, orden.vehiculo_id, 99) if con_orden else None
    _revisada(db_ordenes, primera["solicitud_id"], "aceptada", nueva.orden_id if nueva else None)
    assert _solicitar(api_ordenes, orden).status_code == 409
    assert _solicitar(api_ordenes, orden, "Otra atención").status_code == 409
    if nueva:
        detalle = api_ordenes.get(f"{BASE}/{primera['solicitud_id']}", headers=CLIENTE)
        assert detalle.json()["orden_generada_id"] == nueva.orden_id
        pagina = api_ordenes.get(BASE, headers=CLIENTE, params={
            "orden_generada_id": nueva.orden_id, "situacion": "aceptada",
        }).json()
        assert pagina["total"] == 1 and pagina["items"] == [detalle.json()]


def test_rechazada_permite_otra_y_conserva_antecedente(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    primera = _solicitar(api_ordenes, orden).json()
    _revisada(db_ordenes, primera["solicitud_id"], "rechazada")
    segunda = _solicitar(api_ordenes, orden)
    assert segunda.status_code == 201
    assert segunda.json()["solicitud_id"] != primera["solicitud_id"]
    respuesta = api_ordenes.get(BASE, headers=CLIENTE).json()
    assert respuesta["total"] == 2
    assert [s["situacion"] for s in respuesta["items"]] == ["pendiente", "rechazada"]


@pytest.mark.parametrize("estado", range(1, 8))
def test_solo_antecedente_cancelado(api_ordenes, db_ordenes, estado):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=estado)
    assert _solicitar(api_ordenes, orden).status_code == 409
    assert db_ordenes.scalar(select(func.count()).select_from(SolicitudNuevaAtencion)) == 0


@pytest.mark.parametrize("headers,esperado", [
    ({}, 401), (ADMIN, 403), (_headers_para(50, NombreRol.MECANICO), 403),
    (_headers_para(77, NombreRol.CLIENTE), 404),
    (_headers_para(99, NombreRol.CLIENTE, NombreRol.ADMINISTRADOR), 404),
    (_headers_para(10, NombreRol.CLIENTE, NombreRol.ADMINISTRADOR), 201),
    (_headers_para(10, NombreRol.CLIENTE, NombreRol.MECANICO), 201),
])
def test_creacion_respeta_rol_y_propiedad_incluso_multirrol(api_ordenes, db_ordenes, headers, esperado):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    assert _solicitar(api_ordenes, orden, headers=headers).status_code == esperado


@pytest.mark.parametrize("body", [None, {}, {"descripcion": ""}, {"descripcion": " \t\n "},
    {"descripcion": "x" * 2001}, {"descripcion": "OK", "cliente_usuario_id": 99},
    {"descripcion": "OK", "solicitada_en": "2026-11-08T00:00:00Z"},
    {"descripcion": "OK", "situacion": "aceptada"}, {"descripcion": 123},
])
def test_body_valida_descripcion_y_rechaza_campos_inyectados(api_ordenes, body):
    respuesta = api_ordenes.post("/ordenes/1/nueva-atencion", headers=CLIENTE,
                                 **({} if body is None else {"json": body}))
    assert respuesta.status_code == 422


def test_acepta_limite_exacto_y_orden_inexistente_es_404(api_ordenes, db_ordenes):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    assert _solicitar(api_ordenes, orden, "x" * 2000).status_code == 201
    assert api_ordenes.post("/ordenes/999/nueva-atencion", headers=CLIENTE,
                           json={"descripcion": "Consultar"}).status_code == 404


@pytest.mark.parametrize("roles,usuario,ids", [
    ((NombreRol.CLIENTE,), 10, [10]),
    ((NombreRol.CLIENTE, NombreRol.MECANICO), 10, [10]),
    ((NombreRol.ADMINISTRADOR,), 99, [10, 20]),
    ((NombreRol.CLIENTE, NombreRol.ADMINISTRADOR), 10, [10, 20]),
])
def test_visibilidad_listado_y_detalle(api_ordenes, db_ordenes, roles, usuario, ids):
    solicitudes = []
    for propietario in (10, 20):
        orden = _crear_orden(db_ordenes, propietario, estado_codigo=CANCELADO)
        solicitudes.append(_solicitar(api_ordenes, orden, headers=_headers_para(propietario, NombreRol.CLIENTE)).json())
    headers = _headers_para(usuario, *roles)
    respuesta = api_ordenes.get(BASE, headers=headers)
    assert respuesta.status_code == 200  # no queda atrapada por GET /ordenes/{id}
    assert sorted(s["cliente_usuario_id"] for s in respuesta.json()["items"]) == ids
    for solicitud in solicitudes:
        detalle = api_ordenes.get(f"{BASE}/{solicitud['solicitud_id']}", headers=headers)
        assert detalle.status_code == (200 if solicitud["cliente_usuario_id"] in ids else 404)
        if detalle.status_code == 200:
            assert detalle.json() == solicitud


@pytest.mark.parametrize("headers,estado", [({}, 401), (_headers_para(50, NombreRol.MECANICO), 403)])
def test_consultas_rechazan_sin_rol_permitido(api_ordenes, headers, estado):
    assert api_ordenes.get(BASE, headers=headers).status_code == estado
    assert api_ordenes.get(f"{BASE}/1", headers=headers).status_code == estado


def test_lista_vacia_paginacion_y_filtros(api_ordenes, db_ordenes):
    assert api_ordenes.get(BASE, headers=CLIENTE).json() == {"items": [], "total": 0, "limit": 20, "offset": 0}
    solicitudes = []
    for _ in range(3):
        orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
        solicitudes.append(_solicitar(api_ordenes, orden).json())
    # Empate de fechas: el ID descendente desempata de manera estable.
    fecha = datetime.now(timezone.utc)
    for s in db_ordenes.scalars(select(SolicitudNuevaAtencion)):
        s.solicitada_en = fecha
    db_ordenes.commit()
    pagina = api_ordenes.get(BASE, headers=CLIENTE, params={"limit": 1, "offset": 1}).json()
    assert pagina["total"] == 3 and pagina["items"][0]["solicitud_id"] == solicitudes[1]["solicitud_id"]
    filtrada = api_ordenes.get(BASE, headers=CLIENTE, params={"orden_cancelada_id": solicitudes[0]["orden_cancelada_id"], "situacion": "pendiente"}).json()
    assert filtrada["total"] == 1
    assert api_ordenes.get(BASE, headers=CLIENTE, params={"orden_generada_id": 999}).json()["total"] == 0
    assert api_ordenes.get(f"{BASE}/999", headers=CLIENTE).status_code == 404


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1},
    {"situacion": "completada"}, {"orden_cancelada_id": 0}, {"orden_generada_id": -1}])
def test_query_invalida(api_ordenes, params):
    assert api_ordenes.get(BASE, headers=CLIENTE, params=params).status_code == 422


@pytest.mark.parametrize("identificador", [0, -1, "abc"])
def test_identificadores_invalidos(api_ordenes, identificador):
    assert api_ordenes.get(f"{BASE}/{identificador}", headers=CLIENTE).status_code == 422
    assert api_ordenes.post(f"/ordenes/{identificador}/nueva-atencion", headers=CLIENTE,
                           json={"descripcion": "Revisar"}).status_code == 422


@pytest.mark.parametrize("punto", ["flush", "commit"])
def test_fallo_de_escritura_revierte_solicitud_y_permite_reintentar(api_ordenes, db_ordenes, monkeypatch, punto):
    orden = _crear_orden(db_ordenes, 10, estado_codigo=CANCELADO)
    original = getattr(db_ordenes, punto)
    def fallar(*args, **kwargs):
        if punto == "commit" or db_ordenes.new:
            raise SQLAlchemyError("fallo de escritura de prueba")
        return original(*args, **kwargs)
    with monkeypatch.context() as p:
        p.setattr(db_ordenes, punto, fallar)
        assert _solicitar(api_ordenes, orden).status_code == 500
    assert db_ordenes.scalar(select(func.count()).select_from(SolicitudNuevaAtencion)) == 0
    assert _solicitar(api_ordenes, orden).status_code == 201
