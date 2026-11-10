"""Entrega C: revisión inmutable y orden vinculada atómica, por HTTP."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from services.ms2_taller.models import (
    ConfiguracionCupoIngresos, EventoOutbox, HistorialEstado, HistorialValidacionCupoIngreso,
    IngresoVehiculo, OrdenTrabajo, SolicitudNuevaAtencion,
)
from services.ms2_taller.services.ordenes import crear_orden, registrar_devolucion_fisica
from services.ms1_auth.schemas.notificacion import EventoRevisionNuevaAtencion
from shared.auth import NombreRol
from test_ordenes_api import api_ordenes, db_ordenes, _crear_orden, _headers_para  # noqa: F401

ADMIN = _headers_para(99, NombreRol.ADMINISTRADOR)
CLIENTE = _headers_para(10, NombreRol.CLIENTE)
BASE = "/ordenes/nuevas-atenciones"


def _nueva(api, db):
    orden = _crear_orden(db, 10, estado_codigo=8)
    r = api.post(f"/ordenes/{orden.orden_id}/nueva-atencion", headers=CLIENTE, json={"descripcion": "Revisar frenos"})
    assert r.status_code == 201
    return orden, r.json()["solicitud_id"]


def _revisar(api, solicitud_id, decision="aceptada", respuesta="Podemos atenderlo", headers=ADMIN):
    return api.post(f"{BASE}/{solicitud_id}/revision", headers=headers,
                    json={"decision": decision, "respuesta": respuesta})


def _generar(api, solicitud_id, headers=ADMIN):
    return api.post(f"{BASE}/{solicitud_id}/orden", headers=headers, json={})


@pytest.mark.parametrize("decision", ["aceptada", "rechazada"])
def test_revision_guarda_auditoria_y_evento_juntos_sin_transicion_de_orden(api_ordenes, db_ordenes, decision):
    orden, sid = _nueva(api_ordenes, db_ordenes)
    r = _revisar(api_ordenes, sid, decision, "  Respuesta del taller  ")
    assert r.status_code == 200
    s = r.json()
    assert s["situacion"] == decision and s["respuesta"] == "Respuesta del taller"
    assert s["revisor_id"] == 99 and s["revisada_en"]
    assert s["orden_generada_id"] is None
    e = db_ordenes.scalar(select(EventoOutbox).where(EventoOutbox.tipo == "nueva_atencion.revisada"))
    assert e.tipo == "nueva_atencion.revisada" and e.publicado_en is None
    evento = EventoRevisionNuevaAtencion.model_validate(e.payload)
    assert (evento.solicitud_id, evento.cliente_usuario_id, evento.revisor_id, evento.decision) == (sid, 10, 99, decision)
    assert db_ordenes.scalar(select(func.count()).select_from(HistorialEstado)) == 0
    assert db_ordenes.get(OrdenTrabajo, orden.orden_id).estado_codigo == 8
    assert db_ordenes.get(IngresoVehiculo, orden.ingreso_id).salida_en is None
    assert api_ordenes.get(f"{BASE}/{sid}", headers=CLIENTE).json() == s


def test_revision_identica_por_otro_admin_conserva_actor_fecha_y_un_solo_evento(api_ordenes, db_ordenes):
    _, sid = _nueva(api_ordenes, db_ordenes)
    primera = _revisar(api_ordenes, sid)
    segunda = _revisar(api_ordenes, sid, respuesta="  Podemos atenderlo  ", headers=_headers_para(100, NombreRol.ADMINISTRADOR))
    assert primera.status_code == segunda.status_code == 200
    assert primera.json() == segunda.json()
    assert db_ordenes.scalar(select(func.count()).select_from(EventoOutbox)) == 2
    assert _revisar(api_ordenes, sid, "rechazada").status_code == 409
    assert _revisar(api_ordenes, sid, respuesta="Otro contenido").status_code == 409
    assert api_ordenes.get(f"{BASE}/{sid}", headers=ADMIN).json() == primera.json()


def test_autorrevision_multirrol_permitida_y_sin_maximo_inventado(api_ordenes, db_ordenes):
    _, sid = _nueva(api_ordenes, db_ordenes)
    r = _revisar(api_ordenes, sid, respuesta="x" * 6000, headers=_headers_para(10, NombreRol.CLIENTE, NombreRol.ADMINISTRADOR))
    assert r.status_code == 200 and r.json()["revisor_id"] == 10
    assert len(r.json()["respuesta"]) == 6000


@pytest.mark.parametrize("devuelta", [False, True])
def test_generacion_guarda_orden_y_vinculo_y_respeta_ingreso_fisico(api_ordenes, db_ordenes, devuelta):
    anterior, sid = _nueva(api_ordenes, db_ordenes)
    _revisar(api_ordenes, sid)
    if devuelta:
        registrar_devolucion_fisica(db_ordenes, orden_id=anterior.orden_id, administrador_id=99)
    r = _generar(api_ordenes, sid)
    assert r.status_code == 201
    s, o = r.json()["solicitud"], r.json()["orden"]
    assert s["orden_generada_id"] == o["orden_id"] != anterior.orden_id
    assert o["estado_codigo"] == 1 and o["mecanico_actual_id"] is None and o["creado_por_id"] == 99
    assert o["vehiculo_id"] == anterior.vehiculo_id
    assert (o["ingreso_id"] != anterior.ingreso_id) == devuelta
    assert db_ordenes.scalar(select(func.count()).select_from(IngresoVehiculo)) == (2 if devuelta else 1)
    assert db_ordenes.scalar(select(func.count()).select_from(HistorialValidacionCupoIngreso)) == int(devuelta)
    historial = db_ordenes.scalar(select(HistorialEstado))
    assert historial.orden_id == o["orden_id"] and historial.estado_anterior is None and historial.estado_nuevo == 1
    assert historial.actor_usuario_id == 99
    assert db_ordenes.get(OrdenTrabajo, anterior.orden_id).estado_codigo == 8
    assert db_ordenes.scalar(select(func.count()).select_from(EventoOutbox)) == 3


def test_generacion_reintenta_sin_duplicar_y_devuelve_estado_actual_de_orden(api_ordenes, db_ordenes):
    _, sid = _nueva(api_ordenes, db_ordenes)
    _revisar(api_ordenes, sid)
    primera = _generar(api_ordenes, sid)
    oid = primera.json()["orden"]["orden_id"]
    asignada = api_ordenes.put(f"/ordenes/{oid}/mecanico", headers=ADMIN, json={"mecanico_id": 50})
    assert asignada.status_code == 200
    segunda = _generar(api_ordenes, sid, _headers_para(100, NombreRol.ADMINISTRADOR))
    assert segunda.status_code == 200
    assert segunda.json()["orden"]["orden_id"] == oid
    assert segunda.json()["orden"]["estado_codigo"] == 2
    assert segunda.json()["orden"]["creado_por_id"] == 99
    assert db_ordenes.scalar(select(func.count()).select_from(OrdenTrabajo)) == 2


@pytest.mark.parametrize("situacion", ["pendiente", "rechazada"])
def test_no_genera_sin_aceptacion(api_ordenes, db_ordenes, situacion):
    _, sid = _nueva(api_ordenes, db_ordenes)
    if situacion == "rechazada":
        _revisar(api_ordenes, sid, "rechazada")
    assert _generar(api_ordenes, sid).status_code == 409
    assert db_ordenes.get(SolicitudNuevaAtencion, sid).orden_generada_id is None
    assert db_ordenes.scalar(select(func.count()).select_from(OrdenTrabajo)) == 1


def test_otra_orden_activa_impide_generar_sin_escrituras_adicionales(api_ordenes, db_ordenes):
    anterior, sid = _nueva(api_ordenes, db_ordenes)
    _revisar(api_ordenes, sid)
    activa = crear_orden(db_ordenes, anterior.vehiculo_id, 99)
    antes = db_ordenes.scalar(select(func.count()).select_from(EventoOutbox))
    r = _generar(api_ordenes, sid)
    assert r.status_code == 409 and f"n° {activa.orden_id}" in r.json()["detail"]
    assert db_ordenes.get(SolicitudNuevaAtencion, sid).orden_generada_id is None
    assert db_ordenes.scalar(select(func.count()).select_from(EventoOutbox)) == antes


@pytest.mark.parametrize("maximo", [None, 1])
def test_rechazo_cupo_revierte_y_audita_datos_originales_aparte(api_ordenes, db_ordenes, maximo):
    anterior, sid = _nueva(api_ordenes, db_ordenes)
    _revisar(api_ordenes, sid)
    registrar_devolucion_fisica(db_ordenes, orden_id=anterior.orden_id, administrador_id=99)
    db_ordenes.get(ConfiguracionCupoIngresos, 1).max_ingresos_diarios = maximo
    db_ordenes.commit()
    assert _generar(api_ordenes, sid).status_code == 409
    auditoria = db_ordenes.scalar(select(HistorialValidacionCupoIngreso))
    assert auditoria and not auditoria.aceptada and auditoria.ingreso_id is None
    assert auditoria.max_ingresos_diarios == maximo and auditoria.ingresos_registrados == 1
    assert auditoria.administrador_id == 99
    assert db_ordenes.get(SolicitudNuevaAtencion, sid).orden_generada_id is None
    assert db_ordenes.scalar(select(func.count()).select_from(OrdenTrabajo)) == 1
    assert db_ordenes.scalar(select(func.count()).select_from(IngresoVehiculo)) == 1


def test_fallo_auditoria_de_rechazo_responde_500_sin_datos_parciales(api_ordenes, db_ordenes, monkeypatch):
    import services.ms2_taller.services.nuevas_atenciones as servicio
    from services.ms2_taller.services.cupo_ingresos import PersistenciaCupoIngresosError
    anterior, sid = _nueva(api_ordenes, db_ordenes)
    _revisar(api_ordenes, sid)
    registrar_devolucion_fisica(db_ordenes, orden_id=anterior.orden_id, administrador_id=99)
    db_ordenes.get(ConfiguracionCupoIngresos, 1).max_ingresos_diarios = 1
    db_ordenes.commit()
    def fallar(*args):
        raise PersistenciaCupoIngresosError("Fallo de auditoría")
    monkeypatch.setattr(servicio, "registrar_rechazo_cupo", fallar)
    assert _generar(api_ordenes, sid).status_code == 500
    assert db_ordenes.get(SolicitudNuevaAtencion, sid).orden_generada_id is None
    assert db_ordenes.scalar(select(func.count()).select_from(OrdenTrabajo)) == 1
    assert db_ordenes.scalar(select(func.count()).select_from(HistorialValidacionCupoIngreso)) == 0


def test_antecedente_incompatible_no_genera_orden(api_ordenes, db_ordenes):
    anterior, sid = _nueva(api_ordenes, db_ordenes)
    _revisar(api_ordenes, sid)
    anterior.estado_codigo = 7  # fixture histórica incompatible, no transición pública
    db_ordenes.commit()
    assert _generar(api_ordenes, sid).status_code == 409
    assert db_ordenes.get(SolicitudNuevaAtencion, sid).orden_generada_id is None


def test_cadena_nueva_cancelacion_solicita_sobre_la_orden_generada(api_ordenes, db_ordenes):
    original, sid = _nueva(api_ordenes, db_ordenes)
    _revisar(api_ordenes, sid)
    oid = _generar(api_ordenes, sid).json()["orden"]["orden_id"]
    assert api_ordenes.post(f"/ordenes/{oid}/cancelacion", headers=CLIENTE, json={"motivo": "No continuaré"}).status_code == 201
    assert api_ordenes.post(f"/ordenes/{oid}/cancelacion/confirmacion", headers=ADMIN).status_code == 200
    assert api_ordenes.post(f"/ordenes/{original.orden_id}/nueva-atencion", headers=CLIENTE, json={"descripcion": "Otra"}).status_code == 409
    siguiente = api_ordenes.post(f"/ordenes/{oid}/nueva-atencion", headers=CLIENTE, json={"descripcion": "Nueva atención de la cancelada más reciente"})
    assert siguiente.status_code == 201
    siguiente_id = siguiente.json()["solicitud_id"]
    assert _revisar(api_ordenes, siguiente_id).status_code == 200
    tercera = _generar(api_ordenes, siguiente_id)
    assert tercera.status_code == 201
    assert tercera.json()["orden"]["ingreso_id"] == original.ingreso_id
    assert db_ordenes.get(SolicitudNuevaAtencion, sid).orden_generada_id == oid
    assert db_ordenes.scalar(select(func.count()).select_from(OrdenTrabajo)) == 3


@pytest.mark.parametrize("endpoint", ["revision", "orden"])
@pytest.mark.parametrize("headers,codigo", [({}, 401), (CLIENTE, 403),
    (_headers_para(50, NombreRol.MECANICO), 403),
    (_headers_para(10, NombreRol.CLIENTE, NombreRol.MECANICO), 403)])
def test_escrituras_solo_admin(api_ordenes, db_ordenes, endpoint, headers, codigo):
    _, sid = _nueva(api_ordenes, db_ordenes)
    body = {} if endpoint == "orden" else {"decision": "aceptada", "respuesta": "OK"}
    assert api_ordenes.post(f"{BASE}/{sid}/{endpoint}", headers=headers, json=body).status_code == codigo


@pytest.mark.parametrize("body", [{}, {"decision": "pendiente", "respuesta": "OK"},
    {"decision": "aceptada", "respuesta": " \t "}, {"decision": "rechazada"},
    {"decision": "aceptada", "respuesta": "OK", "revisor_id": 10},
    {"decision": "aceptada", "respuesta": "OK", "revisada_en": "2026-01-01T00:00:00Z"}])
def test_revision_body_rechaza_contenido_invalido_y_auditoria_inyectada(api_ordenes, body):
    assert api_ordenes.post(f"{BASE}/1/revision", headers=ADMIN, json=body).status_code == 422


@pytest.mark.parametrize("body", [None, {"orden_id": 10}, {"creado_por_id": 10}])
def test_generacion_body_vacio_obligatorio(api_ordenes, body):
    assert api_ordenes.post(f"{BASE}/1/orden", headers=ADMIN, **({} if body is None else {"json": body})).status_code == 422


@pytest.mark.parametrize("endpoint", ["revision", "orden"])
def test_id_y_recurso_inexistente(api_ordenes, endpoint):
    body = {} if endpoint == "orden" else {"decision": "aceptada", "respuesta": "OK"}
    for identificador, codigo in [(0, 422), (-1, 422), ("abc", 422), (999, 404)]:
        assert api_ordenes.post(f"{BASE}/{identificador}/{endpoint}", headers=ADMIN, json=body).status_code == codigo


@pytest.mark.parametrize("punto", ["flush", "commit"])
def test_fallo_revision_revierte_auditoria_y_outbox(api_ordenes, db_ordenes, monkeypatch, punto):
    _, sid = _nueva(api_ordenes, db_ordenes)
    original = getattr(db_ordenes, punto)
    def fallar(*args, **kwargs):
        if punto == "commit" or db_ordenes.new or db_ordenes.dirty:
            raise SQLAlchemyError("fallo de revisión")
        return original(*args, **kwargs)
    with monkeypatch.context() as p:
        p.setattr(db_ordenes, punto, fallar)
        assert _revisar(api_ordenes, sid).status_code == 500
    db_ordenes.expire_all()
    s = db_ordenes.get(SolicitudNuevaAtencion, sid)
    assert s.situacion == "pendiente" and s.revisor_id is s.revisada_en is s.respuesta is None
    assert db_ordenes.scalar(select(func.count()).select_from(EventoOutbox)) == 1


@pytest.mark.parametrize("devuelta", [False, True])
@pytest.mark.parametrize("punto", ["historial", "outbox", "vinculo", "commit"])
def test_fallo_generacion_revierte_orden_ingreso_historial_outbox_y_vinculo(api_ordenes, db_ordenes, monkeypatch, devuelta, punto):
    import services.ms2_taller.services.ordenes as ordenes
    anterior, sid = _nueva(api_ordenes, db_ordenes)
    _revisar(api_ordenes, sid)
    if devuelta:
        registrar_devolucion_fisica(db_ordenes, orden_id=anterior.orden_id, administrador_id=99)
    flush_original = db_ordenes.flush
    historial_original = ordenes.registrar_historial_estado
    def fallar_historial(*args, **kwargs):
        historial_original(*args, **kwargs)
        raise SQLAlchemyError("fallo tras agregar historial")
    def fallar_flush(*args, **kwargs):
        if punto == "outbox" and any(isinstance(x, EventoOutbox) for x in db_ordenes.new):
            raise SQLAlchemyError("fallo al escribir outbox")
        if punto == "vinculo" and any(isinstance(x, SolicitudNuevaAtencion) and x.orden_generada_id is not None for x in db_ordenes.dirty):
            raise SQLAlchemyError("fallo al vincular")
        return flush_original(*args, **kwargs)
    with monkeypatch.context() as p:
        if punto == "historial":
            p.setattr(ordenes, "registrar_historial_estado", fallar_historial)
        elif punto == "commit":
            p.setattr(db_ordenes, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError("fallo de commit")))
        else:
            p.setattr(db_ordenes, "flush", fallar_flush)
        assert _generar(api_ordenes, sid).status_code == 500
    db_ordenes.expire_all()
    assert db_ordenes.get(SolicitudNuevaAtencion, sid).orden_generada_id is None
    for modelo, cantidad in [(OrdenTrabajo, 1), (IngresoVehiculo, 1), (HistorialEstado, 0), (EventoOutbox, 2), (HistorialValidacionCupoIngreso, 0)]:
        assert db_ordenes.scalar(select(func.count()).select_from(modelo)) == cantidad
    # En producción el siguiente HTTP usa otra Session. SQLite reutiliza IDs
    # tras rollback; descartar las identidades de esta Session de prueba.
    db_ordenes.expunge_all()
    assert _generar(api_ordenes, sid).status_code == 201
