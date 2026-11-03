"""Prueba de contrato completa MS2 outbox → MS1 aviso, sin red externa."""
from __future__ import annotations

import asyncio
from datetime import timezone
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms1_auth.config import settings as settings_ms1
from services.ms1_auth.db import get_db as get_db_ms1
from services.ms1_auth.main import app as app_ms1
from services.ms1_auth.models import Base as BaseMS1, Notificacion, Rol, Usuario, UsuarioRol
from services.ms1_auth.schemas.notificacion import EventoEstadoOrden
from services.ms2_taller.config import settings as settings_ms2
from services.ms2_taller.models import (
    Base as BaseMS2,
    Cliente,
    EstadoOrden,
    EventoOutbox,
    IngresoVehiculo,
    OrdenTrabajo,
    Vehiculo,
)
from services.ms2_taller.services import ordenes as servicio_ordenes
from services.ms2_taller.services import publicador_eventos as publicador


def _fabrica(base):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if base is BaseMS2:
        @event.listens_for(engine, "connect")
        def funciones(conexion, _registro):
            conexion.create_function("btrim", 1, lambda valor: valor.strip() if valor else valor)
            conexion.create_function("char_length", 1, lambda valor: len(valor) if valor else 0)
            conexion.execute("PRAGMA foreign_keys=ON")
    base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def test_evento_ms2_llega_a_ms1_y_crea_un_solo_aviso(monkeypatch):
    engine_ms1, fabrica_ms1 = _fabrica(BaseMS1)
    engine_ms2, fabrica_ms2 = _fabrica(BaseMS2)
    secreto = "secreto-dedicado-local-ms1-ms2-para-test"
    original_secreto_ms1 = settings_ms1.EVENT_SHARED_SECRET
    original_secreto_ms2 = settings_ms2.EVENT_SHARED_SECRET
    original_url_ms1 = settings_ms2.MS1_URL
    original_session_local = publicador.SessionLocal

    with fabrica_ms1() as db:
        rol_cliente = Rol(nombre="cliente")
        db.add(rol_cliente)
        usuario = Usuario(
            correo="cliente@example.com",
            nombre="Cliente",
            contrasena_hash="hash-test",
            activo=True,
        )
        db.add(usuario)
        db.flush()
        db.add(UsuarioRol(usuario_id=usuario.usuario_id, rol=rol_cliente))
        db.commit()
        usuario_id = usuario.usuario_id

    with fabrica_ms2() as db:
        db.add_all([
            EstadoOrden(estado_codigo=4, nombre="Esperando repuestos"),
            EstadoOrden(estado_codigo=5, nombre="En reparación"),
        ])
        cliente = Cliente(usuario_id=usuario_id)
        vehiculo = Vehiculo(
            cliente=cliente, patente="EVT123", marca="Marca", modelo="Modelo"
        )
        db.add(vehiculo)
        db.flush()
        ingreso = IngresoVehiculo(vehiculo_id=vehiculo.vehiculo_id, registrado_por_id=99)
        db.add(ingreso)
        db.flush()
        orden = OrdenTrabajo(
            vehiculo_id=vehiculo.vehiculo_id,
            ingreso_id=ingreso.ingreso_id,
            estado_codigo=4,
            creado_por_id=99,
        )
        db.add(orden)
        db.flush()
        servicio_ordenes.registrar_historial_estado(
            db,
            orden_id=orden.orden_id,
            estado_anterior=4,
            estado_nuevo=5,
            actor_usuario_id=99,
            origen="usuario",
        )
        db.commit()
        orden_id = orden.orden_id

    def dependencia_ms1():
        with fabrica_ms1() as db:
            yield db

    app_ms1.dependency_overrides[get_db_ms1] = dependencia_ms1
    monkeypatch.setattr(settings_ms1, "EVENT_SHARED_SECRET", SecretStr(secreto))
    monkeypatch.setattr(settings_ms2, "EVENT_SHARED_SECRET", SecretStr(secreto))
    monkeypatch.setattr(settings_ms2, "MS1_URL", "http://ms1.test")
    monkeypatch.setattr(publicador, "SessionLocal", fabrica_ms2)
    transporte = httpx.ASGITransport(app=app_ms1)

    async def publicar() -> bool:
        async with httpx.AsyncClient(transport=transporte) as cliente_http:
            return await publicador.publicar_siguiente_evento(cliente_http)

    try:
        assert asyncio.run(publicar()) is True
        assert asyncio.run(publicar()) is False
        with fabrica_ms1() as db:
            avisos = list(db.scalars(select(Notificacion)))
            assert len(avisos) == 1
            assert avisos[0].destinatario_id == usuario_id
            assert avisos[0].orden_id == orden_id
            evento_id = avisos[0].evento_id
        with fabrica_ms2() as db:
            outbox = db.scalar(select(EventoOutbox))
            assert outbox is not None
            assert outbox.evento_id == evento_id
            assert outbox.publicado_en is not None
    finally:
        app_ms1.dependency_overrides.clear()
        settings_ms1.EVENT_SHARED_SECRET = original_secreto_ms1
        settings_ms2.EVENT_SHARED_SECRET = original_secreto_ms2
        settings_ms2.MS1_URL = original_url_ms1
        publicador.SessionLocal = original_session_local
        engine_ms1.dispose()
        engine_ms2.dispose()


def test_contrato_rechaza_fechas_sin_zona_estados_invalidos_y_campos_extra():
    base = {
        "evento_id": str(uuid4()),
        "tipo": "orden.estado_cambiado",
        "ocurrido_en": "2026-10-23T10:00:00+00:00",
        "orden_id": 1,
        "vehiculo_id": 1,
        "cliente_usuario_id": 1,
        "estado_anterior": 4,
        "estado_nuevo": 5,
    }
    evento = EventoEstadoOrden.model_validate(base)
    assert evento.ocurrido_en.utcoffset() == timezone.utc.utcoffset(evento.ocurrido_en)

    for cambios in (
        {"ocurrido_en": "2026-10-23T10:00:00"},
        {"estado_nuevo": 99},
        {"estado_nuevo": 4},
        {"texto_libre": "no se acepta contenido externo"},
    ):
        with pytest.raises(ValidationError):
            EventoEstadoOrden.model_validate({**base, **cambios})
