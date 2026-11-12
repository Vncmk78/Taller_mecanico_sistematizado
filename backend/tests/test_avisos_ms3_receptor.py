"""Destinatarios por dominio y recepción idempotente de hechos de MS3."""

from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from services.ms1_auth.config import settings
from services.ms1_auth.models import EntregaNotificacion, Notificacion
from services.ms1_auth.routers import avisos_ms3 as receptor
from shared.contratos_avisos import DestinatarioOrden
from test_notificaciones_api import _crear_cliente
from test_solicitud_nueva_atencion_notificaciones import admin

SECRETO = "credencial-exclusiva-ms3-notificaciones-123456"
RUTA = "/interno/eventos/ms3/aviso"
H = {"X-Service-Token": SECRETO}


def evento(tipo="presupuesto.enviado", **extra):
    datos = dict(
        evento_id=str(uuid4()), ocurrido_en=datetime.now(timezone.utc).isoformat(), tipo=tipo
    )
    if tipo == "stock.alerta":
        datos.update(repuesto_id=9, nombre="Filtro", stock=2, umbral=3)
    else:
        datos.update(presupuesto_id=5, orden_id=123, version=1)
        if tipo == "presupuesto.decidido":
            datos.update(decision_id=6, decision="aprobado")
    return {**datos, **extra}


@pytest.fixture
def configurado(monkeypatch):
    monkeypatch.setattr(settings, "MS3_EVENT_SHARED_SECRET", SecretStr(SECRETO))
    monkeypatch.setattr(
        receptor,
        "resolver_destinatario",
        lambda oid: DestinatarioOrden(orden_id=oid, vehiculo_id=456, cliente_usuario_id=7),
    )


def test_envio_usa_cliente_de_ms2_y_conserva_referencias(api, db, configurado):
    _crear_cliente(db, 7)
    _crear_cliente(db, 8)
    admin(db, 20)
    e = evento()
    a = api.post(RUTA, json=e, headers=H)
    b = api.post(RUTA, json=e, headers=H)
    assert a.status_code == b.status_code == 200
    assert a.json()["creadas"] == b.json()["existentes"] == 1
    n = db.scalar(select(Notificacion))
    assert (n.destinatario_id, n.orden_id, n.presupuesto_id) == (7, 123, 5)
    assert db.scalar(select(func.count()).select_from(Notificacion)) == 1
    assert db.scalar(select(func.count()).select_from(EntregaNotificacion)) == 2


def test_decision_solo_personal_activo_y_stock_solo_correo(api, db, configurado, monkeypatch):
    _crear_cliente(db, 7)
    admin(db, 20)
    admin(db, 21, False)
    assert api.post(RUTA, json=evento("presupuesto.decidido"), headers=H).json()["creadas"] == 1
    monkeypatch.setattr(
        receptor, "resolver_destinatario", lambda _: pytest.fail("Stock no consulta MS2")
    )
    e = evento("stock.alerta")
    assert api.post(RUTA, json=e, headers=H).json()["creadas"] == 1
    assert api.post(RUTA, json=e, headers=H).json()["existentes"] == 1
    ns = list(db.scalars(select(Notificacion).order_by(Notificacion.notificacion_id)))
    assert [n.destinatario_id for n in ns] == [20, 20]
    assert ns[1].repuesto_id == 9 and ns[1].orden_id is None
    canales = list(
        db.scalars(
            select(EntregaNotificacion.canal).where(
                EntregaNotificacion.notificacion_id == ns[1].notificacion_id
            )
        )
    )
    assert canales == ["correo"]


@pytest.mark.parametrize(
    "cambio",
    [
        {"cliente_usuario_id": 8},
        {"correo": "ajeno@example.test"},
        {"orden_id": 0},
        {"ocurrido_en": "2026-11-08T12:00:00"},
        {"tipo": "inventado"},
    ],
)
def test_body_no_puede_elegir_destinatario_ni_inventar_hechos(api, configurado, cambio):
    assert api.post(RUTA, json=evento(**cambio), headers=H).status_code == 422


def test_credenciales_de_ms2_y_jwt_no_sirven_para_ms3(api, monkeypatch):
    monkeypatch.setattr(settings, "MS3_EVENT_SHARED_SECRET", None)
    assert api.post(RUTA, json=evento(), headers=H).status_code == 503
    monkeypatch.setattr(settings, "MS3_EVENT_SHARED_SECRET", SecretStr(SECRETO))
    for h in (
        {},
        {"X-Service-Token": settings.JWT_SECRET_KEY.get_secret_value()},
        {"X-Service-Token": "otra"},
    ):
        assert api.post(RUTA, json=evento(), headers=h).status_code == 401


def test_fallo_de_canales_revierte_todos_los_destinatarios(api, db, configurado, monkeypatch):
    admin(db, 20)
    admin(db, 21)
    with monkeypatch.context() as p:
        p.setattr(db, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError("fallo controlado")))
        assert api.post(RUTA, json=evento("stock.alerta"), headers=H).status_code == 500
    assert db.scalar(select(func.count()).select_from(Notificacion)) == 0
    assert db.scalar(select(func.count()).select_from(EntregaNotificacion)) == 0


def test_lookup_indisponible_no_persiste_y_recupera_mismo_evento(api, db, configurado, monkeypatch):
    _crear_cliente(db, 7)
    e = evento()
    with monkeypatch.context() as p:
        p.setattr(
            settings,
            "MS2_NOTIFICATION_SECRET",
            SecretStr("consulta-interna-exclusiva-ms1-ms2-123456"),
        )
        p.setattr(receptor, "resolver_destinatario", RESOLVER_REAL)

        def caido(*a, **kw):
            raise httpx.ConnectError("caída controlada")

        p.setattr(receptor.httpx, "get", caido)
        assert api.post(RUTA, json=e, headers=H).status_code == 503
    assert db.scalar(select(func.count()).select_from(Notificacion)) == 0
    assert api.post(RUTA, json=e, headers=H).json()["creadas"] == 1


RESOLVER_REAL = receptor.resolver_destinatario


def test_lookup_valida_identidad_y_no_incluye_pii(monkeypatch):
    monkeypatch.setattr(
        settings, "MS2_NOTIFICATION_SECRET", SecretStr("consulta-interna-exclusiva-ms1-ms2-123456")
    )

    def responder(url, headers, timeout):
        assert url.endswith("/interno/notificaciones/ordenes/123/destinatario")
        assert headers == {"X-Service-Token": settings.MS2_NOTIFICATION_SECRET.get_secret_value()}
        return httpx.Response(
            200,
            json={"orden_id": 999, "vehiculo_id": 456, "cliente_usuario_id": 7},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(receptor.httpx, "get", responder)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        RESOLVER_REAL(123)
    assert exc.value.status_code == 503
