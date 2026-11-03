"""Pruebas del contrato interno y la bandeja de notificaciones de MS1."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.ms1_auth.config import settings
from services.ms1_auth.models.notificacion import Notificacion
from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from shared.auth import NombreRol, crear_token_acceso


SECRETO_SERVICIO = "secreto-interno-de-pruebas-ms1-ms2"


def _crear_cliente(db: Session, usuario_id: int) -> Usuario:
    cliente = db.scalar(select(Rol).where(Rol.nombre == NombreRol.CLIENTE.value))
    assert cliente is not None
    usuario = Usuario(
        usuario_id=usuario_id,
        correo=f"cliente-{usuario_id}@example.com",
        nombre=f"Cliente {usuario_id}",
        contrasena_hash="hash-de-prueba",
        activo=True,
    )
    db.add(usuario)
    db.flush()
    db.add(UsuarioRol(usuario_id=usuario_id, rol_id=cliente.rol_id))
    db.commit()
    return usuario


def _evento() -> dict[str, object]:
    return {
        "evento_id": str(uuid4()),
        "tipo": "orden.estado_cambiado",
        "ocurrido_en": datetime.now(timezone.utc).isoformat(),
        "orden_id": 123,
        "vehiculo_id": 456,
        "cliente_usuario_id": 7,
        "estado_anterior": 5,
        "estado_nuevo": 6,
    }


def _jwt(usuario_id: int) -> str:
    return crear_token_acceso(
        usuario_id,
        [NombreRol.CLIENTE],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
    )


def test_evento_interno_crea_aviso_y_reintento_es_idempotente(
    api: TestClient,
    db: Session,
    monkeypatch,
):
    _crear_cliente(db, 7)
    monkeypatch.setattr(settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO_SERVICIO))
    body = _evento()
    headers = {"X-Service-Token": SECRETO_SERVICIO}

    primera = api.post("/interno/eventos/ordenes/estado", json=body, headers=headers)
    segunda = api.post("/interno/eventos/ordenes/estado", json=body, headers=headers)

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert primera.json()["duplicado"] is False
    assert segunda.json()["duplicado"] is True
    assert segunda.json()["notificacion_id"] == primera.json()["notificacion_id"]
    assert db.scalar(select(func.count()).select_from(Notificacion)) == 1


def test_evento_interno_requiere_secreto_dedicado(api: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO_SERVICIO))
    respuesta = api.post(
        "/interno/eventos/ordenes/estado",
        json=_evento(),
        headers={"X-Service-Token": "credencial-incorrecta"},
    )

    assert respuesta.status_code == 401


def test_evento_interno_desactivado_si_no_hay_secreto_configurado(
    api: TestClient, monkeypatch
):
    monkeypatch.setattr(settings, "EVENT_SHARED_SECRET", None)

    respuesta = api.post("/interno/eventos/ordenes/estado", json=_evento())

    assert respuesta.status_code == 503


def test_evento_rechaza_destinatario_que_no_es_cliente_activo(
    api: TestClient, monkeypatch
):
    monkeypatch.setattr(settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO_SERVICIO))

    respuesta = api.post(
        "/interno/eventos/ordenes/estado",
        json=_evento(),
        headers={"X-Service-Token": SECRETO_SERVICIO},
    )

    assert respuesta.status_code == 422


def test_bandeja_solo_devuelve_avisos_del_usuario_autenticado(
    api: TestClient,
    db: Session,
    monkeypatch,
):
    _crear_cliente(db, 7)
    _crear_cliente(db, 8)
    monkeypatch.setattr(settings, "EVENT_SHARED_SECRET", SecretStr(SECRETO_SERVICIO))
    evento = _evento()
    api.post(
        "/interno/eventos/ordenes/estado",
        json=evento,
        headers={"X-Service-Token": SECRETO_SERVICIO},
    )

    respuesta_cliente = api.get(
        "/notificaciones", headers={"Authorization": f"Bearer {_jwt(7)}"}
    )
    respuesta_ajena = api.get(
        "/notificaciones", headers={"Authorization": f"Bearer {_jwt(8)}"}
    )

    assert respuesta_cliente.status_code == respuesta_ajena.status_code == 200
    assert len(respuesta_cliente.json()) == 1
    assert respuesta_cliente.json()[0]["orden_id"] == 123
    assert respuesta_ajena.json() == []
