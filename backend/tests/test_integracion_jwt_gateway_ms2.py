"""SCRUM-358: JWT emitido por MS1 y validado por MS2 vía Gateway real.

Solo se sustituyen las bases de datos y el transporte HTTP externo. Los
routers, la emisión, la validación y la autorización son código productivo.
"""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from gateway.main import app as gateway_app
from gateway.rutas import RUTAS
from services.ms1_auth.config import settings as ms1_settings
from services.ms1_auth.db import get_db as get_db_ms1
from services.ms1_auth.main import app as ms1_app
from services.ms2_taller.config import settings as ms2_settings
from services.ms2_taller.db import get_db as get_db_ms2
from services.ms2_taller.main import app as ms2_app
from services.ms2_taller.models import Base, Cliente, Vehiculo


@pytest.fixture
def db_integracion_ms2() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def registrar_funciones_sqlite(conexion, _registro) -> None:
        # Equivalentes de las funciones usadas en CHECKs de PostgreSQL.
        conexion.create_function(
            "btrim", 1, lambda valor: valor.strip() if valor is not None else None
        )
        conexion.create_function(
            "char_length", 1, lambda valor: len(valor) if valor is not None else None
        )

    Base.metadata.create_all(engine)
    try:
        with sessionmaker(bind=engine, expire_on_commit=False)() as sesion:
            yield sesion
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def gateway_integracion(
    db: Session,
    db_integracion_ms2: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, respx.Route], None, None]:
    secreto = SecretStr("secreto-compartido-solo-test-scrum-358-123456789")
    for configuracion in (ms1_settings, ms2_settings):
        monkeypatch.setattr(configuracion, "JWT_SECRET_KEY", secreto)

    def db_ms1():
        yield db

    def db_ms2():
        yield db_integracion_ms2

    monkeypatch.setitem(ms1_app.dependency_overrides, get_db_ms1, db_ms1)
    monkeypatch.setitem(ms2_app.dependency_overrides, get_db_ms2, db_ms2)
    monkeypatch.setitem(RUTAS, "auth", "http://ms1.test")
    for prefijo in ("vehiculos", "ordenes"):
        monkeypatch.setitem(RUTAS, prefijo, "http://ms2.test")

    async def ejecutar_ms1(request: httpx.Request) -> httpx.Response:
        async with httpx.ASGITransport(app=ms1_app) as transporte:
            respuesta = await transporte.handle_async_request(request)
            await respuesta.aread()
            return respuesta

    async def ejecutar_ms2(request: httpx.Request) -> httpx.Response:
        async with httpx.ASGITransport(app=ms2_app) as transporte:
            respuesta = await transporte.handle_async_request(request)
            await respuesta.aread()
            return respuesta

    # Las respuestas vienen de las aplicaciones reales, no son prefabricadas.
    # Toda conexión HTTP sin una ruta local declarada provoca un fallo.
    with respx.mock(assert_all_mocked=True) as transporte_http:
        transporte_http.route(host="ms1.test").mock(side_effect=ejecutar_ms1)
        ruta_ms2 = transporte_http.route(host="ms2.test").mock(
            side_effect=ejecutar_ms2
        )
        with TestClient(gateway_app) as gateway:
            yield gateway, ruta_ms2


@pytest.mark.parametrize("operacion", ["consulta_permitida", "creacion_prohibida"])
def test_jwt_real_ms1_llega_a_ms2_y_aplica_el_rol(
    gateway_integracion: tuple[TestClient, respx.Route],
    db_integracion_ms2: Session,
    operacion: str,
) -> None:
    gateway, ruta_ms2 = gateway_integracion
    datos = {
        "email": "cliente.integracion@example.com",
        "password": "ClaveSoloPruebas123!",
        "full_name": "Cliente Integración",
    }
    registro = gateway.post("/api/auth/register", json=datos)
    assert registro.status_code == 201
    usuario_id = registro.json()["id"]

    login = gateway.post(
        "/api/auth/login",
        json={"email": datos["email"], "password": datos["password"]},
    )
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["user"]["id"] == usuario_id
    assert login.json()["user"]["roles"] == ["cliente"]
    authorization = f"Bearer {login.json()['access_token']}"

    # El perfil local referencia el sub de MS1 sin compartir base de datos.
    cliente = Cliente(usuario_id=usuario_id)
    otro_cliente = Cliente(usuario_id=usuario_id + 1)
    propio = Vehiculo(cliente=cliente, patente="JWT358", marca="Toyota", modelo="Yaris")
    ajeno = Vehiculo(cliente=otro_cliente, patente="OTRO358", marca="Kia", modelo="Rio")
    db_integracion_ms2.add_all([propio, ajeno])
    db_integracion_ms2.commit()

    headers = {"Authorization": authorization}
    if operacion == "consulta_permitida":
        respuesta = gateway.get("/api/vehiculos", headers=headers)
        assert respuesta.status_code == 200
        assert [vehiculo["vehiculo_id"] for vehiculo in respuesta.json()] == [
            propio.vehiculo_id
        ]
        assert ruta_ms2.calls.last.request.url.path == "/vehiculos"
    else:
        respuesta = gateway.post(
            "/api/ordenes", headers=headers, json={"vehiculo_id": propio.vehiculo_id}
        )
        assert respuesta.status_code == 403
        assert respuesta.json() == {
            "detail": "No tienes permiso para realizar esta operación"
        }
        assert ruta_ms2.calls.last.request.url.path == "/ordenes"

    assert ruta_ms2.call_count == 1
    assert ruta_ms2.calls.last.request.headers["authorization"] == authorization
