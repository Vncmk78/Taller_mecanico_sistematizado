"""Revisión → outbox → aviso MS1, con contrato real y recibo perdido."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from services.ms1_auth.config import settings as ms1_settings
from services.ms1_auth.main import app as ms1_app
from services.ms1_auth.models import Notificacion
from services.ms2_taller.config import settings as ms2_settings
from services.ms2_taller.models import EventoOutbox, SolicitudNuevaAtencion
from services.ms2_taller.services import publicador_eventos as publicador
from test_notificaciones_api import _crear_cliente, _jwt
from test_ordenes_api import api_ordenes, db_ordenes  # noqa: F401
from test_revision_generacion_nueva_atencion_api import _nueva, _revisar

RUTA = "/interno/eventos/nuevas-atenciones/revision"
SECRETO = "secreto-de-servicio-exclusivo-revision-pruebas"


def _evento(decision="aceptada"):
    return {"evento_id": str(uuid4()), "tipo": "nueva_atencion.revisada",
            "ocurrido_en": datetime.now(timezone.utc).isoformat(), "solicitud_id": 12,
            "orden_cancelada_id": 3, "vehiculo_id": 4, "cliente_usuario_id": 10,
            "decision": decision, "revisor_id": 99}


@pytest.mark.parametrize("decision", ["aceptada", "rechazada"])
def test_receptor_autenticado_deduplica_y_bandeja_solo_del_destinatario(api, db, monkeypatch, decision):
    _crear_cliente(db, 10); _crear_cliente(db, 11)
    monkeypatch.setattr(ms1_settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO))
    evento = _evento(decision)
    primera = api.post(RUTA, headers={"X-Service-Token": SECRETO}, json=evento)
    segunda = api.post(RUTA, headers={"X-Service-Token": SECRETO}, json=evento)
    assert primera.status_code == segunda.status_code == 200
    assert not primera.json()["duplicado"] and segunda.json()["duplicado"]
    assert primera.json()["notificacion_id"] == segunda.json()["notificacion_id"]
    bandeja = api.get("/notificaciones", headers={"Authorization": "Bearer " + _jwt(10)}).json()
    assert len(bandeja) == 1 and decision in bandeja[0]["titulo"]
    assert "12" in bandeja[0]["mensaje"] and bandeja[0]["orden_id"] == 3
    assert bandeja[0]["tipo"] == "nueva_atencion.revisada"
    assert api.get("/notificaciones", headers={"Authorization": "Bearer " + _jwt(11)}).json() == []


def test_receptor_no_acepta_jwt_como_credencial_de_servicio(api, monkeypatch):
    monkeypatch.setattr(ms1_settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO))
    assert api.post(RUTA, headers={"Authorization": "Bearer " + _jwt(10)}, json=_evento()).status_code == 401
    monkeypatch.setattr(ms1_settings, "EVENT_SHARED_SECRET", None)
    assert api.post(RUTA, json=_evento()).status_code == 503


@pytest.mark.parametrize("cambio", [{"ocurrido_en": "2026-11-08T12:00:00"}, {"decision": "pendiente"},
    {"estado_nuevo": 7}, {"revisor_id": 0}, {"tipo": "orden.estado_cambiado"}])
def test_evento_no_finge_transicion_y_rechaza_payload_invalido(api, monkeypatch, cambio):
    monkeypatch.setattr(ms1_settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO))
    assert api.post(RUTA, headers={"X-Service-Token": SECRETO}, json={**_evento(), **cambio}).status_code == 422


def test_receptor_rechaza_destinatario_invalido_y_revierte_fallo_de_persistencia(api, db, monkeypatch):
    monkeypatch.setattr(ms1_settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO))
    evento = _evento(); headers = {"X-Service-Token": SECRETO}
    assert api.post(RUTA, headers=headers, json=evento).status_code == 422
    _crear_cliente(db, 10)
    with monkeypatch.context() as p:
        p.setattr(db, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError("fallo de prueba")))
        assert api.post(RUTA, headers=headers, json=evento).status_code == 500
    assert db.scalar(select(func.count()).select_from(Notificacion)) == 0
    assert api.post(RUTA, headers=headers, json=evento).status_code == 200


def test_revision_y_aviso_sobreviven_recibo_perdido_sin_duplicar(api, db, api_ordenes, db_ordenes, monkeypatch):
    _crear_cliente(db, 10)
    _, sid = _nueva(api_ordenes, db_ordenes)
    assert _revisar(api_ordenes, sid).status_code == 200
    monkeypatch.setattr(ms1_settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO))
    monkeypatch.setattr(ms2_settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO))
    monkeypatch.setattr(ms2_settings, "MS1_URL", "http://ms1.test")
    monkeypatch.setattr(publicador, "SessionLocal", sessionmaker(db_ordenes.get_bind(), expire_on_commit=False))
    class ReciboPerdido(httpx.AsyncBaseTransport):
        def __init__(self):
            self.real = httpx.ASGITransport(app=ms1_app)
            self.primera = True
        async def handle_async_request(self, request):
            assert request.url.path == RUTA
            respuesta = await self.real.handle_async_request(request)
            assert respuesta.status_code == 200
            if self.primera:
                self.primera = False
                raise httpx.ReadError("Recibo perdido después de guardar", request=request)
            return respuesta
    transporte = ReciboPerdido()
    async def publicar():
        async with httpx.AsyncClient(transport=transporte) as cliente:
            return await publicador.publicar_siguiente_evento(cliente)
    assert asyncio.run(publicar())
    db_ordenes.expire_all()
    fila = db_ordenes.scalar(select(EventoOutbox))
    assert fila.publicado_en is None and fila.intentos == 1
    assert db_ordenes.get(SolicitudNuevaAtencion, sid).situacion == "aceptada"
    assert db.scalar(select(func.count()).select_from(Notificacion)) == 1
    fila.proxima_tentativa_en = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_ordenes.commit()
    assert asyncio.run(publicar())
    db_ordenes.expire_all()
    fila = db_ordenes.scalar(select(EventoOutbox))
    assert fila.publicado_en is not None and fila.intentos == 2 and fila.ultimo_error is None
    assert db.scalar(select(func.count()).select_from(Notificacion)) == 1
