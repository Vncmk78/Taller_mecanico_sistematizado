"""Canales persistentes, reintentos y propiedad de los dispositivos."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from pydantic import SecretStr
from sqlalchemy import select, func
from sqlalchemy.orm import sessionmaker
from services.ms1_auth.config import settings
from services.ms1_auth.models import (
    DispositivoPush,
    EntregaNotificacion,
    IntentoEntrega,
    Notificacion,
)
from services.ms1_auth.services import entregas_notificaciones as cola
from services.ms1_auth.services import proveedores_notificaciones as proveedores
from test_notificaciones_api import _crear_cliente, _evento, _jwt

SECRETO = "secreto-exclusivo-de-pruebas-canales-123456"
TOKEN = "token-fcm-exclusivo-de-pruebas-" + str(uuid4())


def auth(uid=7):
    return {"Authorization": "Bearer " + _jwt(uid)}


def aviso(api, db, monkeypatch):
    _crear_cliente(db, 7)
    monkeypatch.setattr(settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO))
    r = api.post(
        "/interno/eventos/ordenes/estado", json=_evento(), headers={"X-Service-Token": SECRETO}
    )
    assert r.status_code == 200
    return r.json()["notificacion_id"]


def worker(db, monkeypatch):
    monkeypatch.setattr(cola, "SessionLocal", sessionmaker(db.get_bind(), expire_on_commit=False))


def estado(db, nid, canal="correo"):
    db.expire_all()
    return db.scalar(
        select(EntregaNotificacion).where(
            EntregaNotificacion.notificacion_id == nid, EntregaNotificacion.canal == canal
        )
    )


def test_avisos_y_canales_se_guardan_juntos_sin_duplicar_recibo(api, db, monkeypatch):
    nid = aviso(api, db, monkeypatch)
    assert db.scalar(select(func.count()).select_from(Notificacion)) == 1
    assert estado(db, nid).estado == "pendiente"
    assert estado(db, nid, "push").estado == "sin_dispositivo"
    assert api.get(f"/notificaciones/{nid}/entregas", headers=auth()).status_code == 200
    _crear_cliente(db, 8)
    assert api.get(f"/notificaciones/{nid}/entregas", headers=auth(8)).status_code == 404
    assert api.post(f"/notificaciones/{nid}/reintentos", headers=auth(8)).status_code == 404
    assert api.get(f"/notificaciones/{nid}/entregas").status_code == 401
    n = db.get(Notificacion, nid)
    cola.encolar_canales(db, n)
    db.commit()
    assert db.scalar(select(func.count()).select_from(EntregaNotificacion)) == 2


def test_sin_proveedor_no_afirma_envio_y_conserva_el_intento(api, db, monkeypatch):
    nid = aviso(api, db, monkeypatch)
    worker(db, monkeypatch)
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    assert cola.procesar_siguiente()
    e = estado(db, nid)
    assert e.estado == "sin_configuracion" and e.intentos == 1 and e.aceptada_en is None
    i = db.scalar(select(IntentoEntrega))
    assert i.resultado == "sin_configuracion" and i.finalizado_en
    assert not cola.procesar_siguiente()
    assert api.get("/notificaciones", headers=auth()).json()[0]["notificacion_id"] == nid


def test_fallo_y_recuperacion_sin_duplicar_aviso_y_sin_reenviar_aceptado(api, db, monkeypatch):
    nid = aviso(api, db, monkeypatch)
    worker(db, monkeypatch)

    def fallo(*args):
        raise proveedores.FalloCanal("smtp_sin_confirmacion")

    monkeypatch.setattr(proveedores, "enviar_correo", fallo)
    assert cola.procesar_siguiente()
    assert estado(db, nid).estado == "fallida"
    enviados = []
    monkeypatch.setattr(
        proveedores, "enviar_correo", lambda *args: enviados.append(args) or "message-id-estable"
    )
    r = api.post(f"/notificaciones/{nid}/reintentos", headers=auth())
    assert r.status_code == 200
    assert cola.procesar_siguiente()
    assert estado(db, nid).estado == "aceptada" and estado(db, nid).intentos == 2
    assert db.scalar(select(func.count()).select_from(Notificacion)) == 1
    assert db.scalar(select(func.count()).select_from(IntentoEntrega)) == 2
    api.post(f"/notificaciones/{nid}/reintentos", headers=auth())
    assert not cola.procesar_siguiente() and len(enviados) == 1
    assert "message-id-estable" == estado(db, nid).proveedor_id


def test_registro_propiedad_idempotencia_y_cierre_de_dispositivo(api, db):
    _crear_cliente(db, 7)
    _crear_cliente(db, 8)
    body = {"token": TOKEN, "plataforma": "android"}
    r = api.post("/notificaciones/dispositivos", headers=auth(), json=body)
    assert r.status_code == 201 and "token" not in r.json()
    did = r.json()["dispositivo_id"]
    r2 = api.post("/notificaciones/dispositivos", headers=auth(), json=body)
    assert r2.status_code == 200 and r2.json()["dispositivo_id"] == did
    assert len(api.get("/notificaciones/dispositivos", headers=auth()).json()) == 1
    assert api.get("/notificaciones/dispositivos", headers=auth(8)).json() == []
    assert api.delete(f"/notificaciones/dispositivos/{did}", headers=auth(8)).status_code == 404
    assert api.delete(f"/notificaciones/dispositivos/{did}", headers=auth()).status_code == 204
    assert api.delete(f"/notificaciones/dispositivos/{did}", headers=auth()).status_code == 204
    assert api.get("/notificaciones/dispositivos", headers=auth()).json()[0]["activo"] is False


def test_cambio_de_cuenta_en_mismo_dispositivo_no_entrega_avisos_del_anterior(api, db, monkeypatch):
    _crear_cliente(db, 8)
    nid = aviso(api, db, monkeypatch)
    worker(db, monkeypatch)
    body = {"token": TOKEN, "plataforma": "android"}
    api.post("/notificaciones/dispositivos", headers=auth(), json=body)
    api.post(f"/notificaciones/{nid}/reintentos", headers=auth())
    api.post("/notificaciones/dispositivos", headers=auth(8), json=body)
    enviados = []
    monkeypatch.setattr(proveedores, "enviar_correo", lambda *args: "correo-ok")
    monkeypatch.setattr(proveedores, "enviar_push", lambda *args: enviados.append(args) or "fcm-ok")
    assert cola.procesar_siguiente()
    assert cola.procesar_siguiente()
    db.expire_all()
    push = db.scalar(
        select(EntregaNotificacion).where(
            EntregaNotificacion.notificacion_id == nid,
            EntregaNotificacion.dispositivo_id.is_not(None),
        )
    )
    assert push.estado == "omitida" and enviados == []


def test_fcm_no_registrado_desactiva_token_sin_tocar_aviso(api, db, monkeypatch):
    nid = aviso(api, db, monkeypatch)
    worker(db, monkeypatch)
    api.post(
        "/notificaciones/dispositivos",
        headers=auth(),
        json={"token": TOKEN, "plataforma": "android"},
    )
    api.post(f"/notificaciones/{nid}/reintentos", headers=auth())
    monkeypatch.setattr(proveedores, "enviar_correo", lambda *args: "correo-ok")

    def fallo(*args):
        raise proveedores.FalloCanal("fcm_token_no_registrado", desactivar_dispositivo=True)

    monkeypatch.setattr(proveedores, "enviar_push", fallo)
    assert cola.procesar_siguiente()
    assert cola.procesar_siguiente()
    db.expire_all()
    assert db.scalar(select(DispositivoPush)).activo is False
    assert db.get(Notificacion, nid) is not None


def test_mismo_trabajo_reclamado_no_se_envia_otra_vez(api, db, monkeypatch):
    nid = aviso(api, db, monkeypatch)
    worker(db, monkeypatch)
    e = estado(db, nid)
    e.estado = "procesando"
    e.lease_token = uuid4()
    e.lease_hasta = datetime.now(timezone.utc) + timedelta(seconds=60)
    db.commit()
    enviados = []
    monkeypatch.setattr(proveedores, "enviar_correo", lambda *args: enviados.append(args))
    assert not cola.procesar_siguiente() and enviados == []
