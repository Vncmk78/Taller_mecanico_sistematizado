"""Pruebas HTTP de INT-29: registro y consulta de vehículos propios."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms2_taller.config import settings
from services.ms2_taller.db import get_db
from services.ms2_taller.main import app
from services.ms2_taller.models import Base, Cliente, Vehiculo
from shared.auth import NombreRol, crear_token_acceso

DATOS_VEHICULO = {
    "patente": "ABCD12",
    "marca": "Toyota",
    "modelo": "Yaris",
    "anio": 2021,
    "kilometraje": 45000,
}


@pytest.fixture
def db_ms2() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    sesion = fabrica()
    try:
        yield sesion
    finally:
        sesion.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def api_ms2(db_ms2: Session) -> Generator[TestClient, None, None]:
    def reemplazar_db():
        yield db_ms2

    app.dependency_overrides[get_db] = reemplazar_db
    with TestClient(app) as cliente_http:
        yield cliente_http
    app.dependency_overrides.clear()


def test_sin_token_devuelve_401(api_ms2: TestClient):
    respuesta = api_ms2.get("/vehiculos")

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_token_invalido_devuelve_401(api_ms2: TestClient):
    respuesta = api_ms2.get(
        "/vehiculos",
        headers={"Authorization": "Bearer token-invalido"},
    )

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_token_expirado_devuelve_401(api_ms2: TestClient):
    token = _firmar(
        {
            "sub": "1",
            "roles": [NombreRol.CLIENTE.value],
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
    )

    respuesta = api_ms2.get("/vehiculos", headers=_encabezado(token))

    assert respuesta.status_code == 401


def test_sub_no_entero_devuelve_401(api_ms2: TestClient):
    token = _firmar(
        {
            "sub": "usuario-uuid",
            "roles": [NombreRol.CLIENTE.value],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
    )

    respuesta = api_ms2.get("/vehiculos", headers=_encabezado(token))

    assert respuesta.status_code == 401


def test_cliente_es_permitido(api_ms2: TestClient, db_ms2: Session):
    _crear_cliente(db_ms2, usuario_id=1)

    respuesta = api_ms2.get("/vehiculos", headers=_headers_para(1, NombreRol.CLIENTE))

    assert respuesta.status_code == 200


@pytest.mark.parametrize("rol", [NombreRol.MECANICO, NombreRol.ADMINISTRADOR])
def test_usuario_sin_rol_cliente_recibe_403(api_ms2: TestClient, rol: NombreRol):
    respuesta = api_ms2.get("/vehiculos", headers=_headers_para(1, rol))

    assert respuesta.status_code == 403


def test_usuario_multirol_con_cliente_es_permitido(
    api_ms2: TestClient,
    db_ms2: Session,
):
    _crear_cliente(db_ms2, usuario_id=1)

    respuesta = api_ms2.get(
        "/vehiculos",
        headers=_headers_para(1, NombreRol.MECANICO, NombreRol.CLIENTE),
    )

    assert respuesta.status_code == 200


def test_post_valido_devuelve_201(api_ms2: TestClient, db_ms2: Session):
    cliente = _crear_cliente(db_ms2, usuario_id=1)

    respuesta = api_ms2.post(
        "/vehiculos",
        json=DATOS_VEHICULO,
        headers=_headers_para(1, NombreRol.CLIENTE),
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["patente"] == DATOS_VEHICULO["patente"]
    vehiculo = db_ms2.scalar(select(Vehiculo))
    assert vehiculo is not None
    assert vehiculo.cliente_id == cliente.cliente_id


def test_get_devuelve_vehiculos_del_cliente(api_ms2: TestClient, db_ms2: Session):
    _crear_cliente(db_ms2, usuario_id=1)
    alta = api_ms2.post(
        "/vehiculos",
        json=DATOS_VEHICULO,
        headers=_headers_para(1, NombreRol.CLIENTE),
    )

    respuesta = api_ms2.get("/vehiculos", headers=_headers_para(1, NombreRol.CLIENTE))

    assert alta.status_code == 201
    assert respuesta.status_code == 200
    assert respuesta.json() == [alta.json()]


def test_body_con_cliente_id_devuelve_422(api_ms2: TestClient, db_ms2: Session):
    _crear_cliente(db_ms2, usuario_id=1)

    respuesta = api_ms2.post(
        "/vehiculos",
        json={**DATOS_VEHICULO, "cliente_id": 999},
        headers=_headers_para(1, NombreRol.CLIENTE),
    )

    assert respuesta.status_code == 422


def test_patente_duplicada_devuelve_409(api_ms2: TestClient, db_ms2: Session):
    _crear_cliente(db_ms2, usuario_id=1)
    headers = _headers_para(1, NombreRol.CLIENTE)
    assert api_ms2.post("/vehiculos", json=DATOS_VEHICULO, headers=headers).status_code == 201

    respuesta = api_ms2.post("/vehiculos", json=DATOS_VEHICULO, headers=headers)

    assert respuesta.status_code == 409
    assert db_ms2.scalar(select(func.count()).select_from(Vehiculo)) == 1


def test_cliente_no_ve_vehiculos_de_otro_cliente(
    api_ms2: TestClient,
    db_ms2: Session,
):
    cliente_a = _crear_cliente(db_ms2, usuario_id=1)
    cliente_b = _crear_cliente(db_ms2, usuario_id=2)
    db_ms2.add_all(
        [
            Vehiculo(cliente_id=cliente_a.cliente_id, **DATOS_VEHICULO),
            Vehiculo(
                cliente_id=cliente_b.cliente_id,
                patente="ZZZZ99",
                marca="Nissan",
                modelo="Versa",
            ),
        ]
    )
    db_ms2.commit()

    respuesta = api_ms2.get("/vehiculos", headers=_headers_para(1, NombreRol.CLIENTE))

    assert respuesta.status_code == 200
    assert [vehiculo["patente"] for vehiculo in respuesta.json()] == ["ABCD12"]


def test_listado_vacio_devuelve_200(api_ms2: TestClient, db_ms2: Session):
    _crear_cliente(db_ms2, usuario_id=1)

    respuesta = api_ms2.get("/vehiculos", headers=_headers_para(1, NombreRol.CLIENTE))

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_cliente_sin_perfil_recibe_404_y_no_se_crea(
    api_ms2: TestClient,
    db_ms2: Session,
):
    respuesta = api_ms2.post(
        "/vehiculos",
        json=DATOS_VEHICULO,
        headers=_headers_para(77, NombreRol.CLIENTE),
    )

    assert respuesta.status_code == 404
    assert db_ms2.scalar(select(func.count()).select_from(Cliente)) == 0


def test_error_de_persistencia_hace_rollback(
    api_ms2: TestClient,
    db_ms2: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    _crear_cliente(db_ms2, usuario_id=1)
    rollback_real = db_ms2.rollback
    flush_real = db_ms2.flush
    rollbacks = 0

    def rollback_controlado() -> None:
        nonlocal rollbacks
        rollbacks += 1
        rollback_real()

    def fallar_flush(*args, **kwargs) -> None:
        raise SQLAlchemyError("fallo simulado")

    monkeypatch.setattr(db_ms2, "rollback", rollback_controlado)
    monkeypatch.setattr(db_ms2, "flush", fallar_flush)

    respuesta = api_ms2.post(
        "/vehiculos",
        json=DATOS_VEHICULO,
        headers=_headers_para(1, NombreRol.CLIENTE),
    )

    assert respuesta.status_code == 500
    assert rollbacks == 1
    monkeypatch.setattr(db_ms2, "flush", flush_real)
    assert db_ms2.scalar(select(func.count()).select_from(Vehiculo)) == 0


def test_openapi_declara_seguridad_bearer(api_ms2: TestClient):
    esquema = api_ms2.get("/openapi.json").json()

    assert esquema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert {"HTTPBearer": []} in esquema["paths"]["/vehiculos"]["post"]["security"]
    assert {"HTTPBearer": []} in esquema["paths"]["/vehiculos"]["get"]["security"]


def _crear_cliente(db: Session, usuario_id: int) -> Cliente:
    cliente = Cliente(usuario_id=usuario_id)
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def _headers_para(usuario_id: int, *roles: NombreRol) -> dict[str, str]:
    token = crear_token_acceso(
        usuario_id,
        roles,
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )
    return _encabezado(token)


def _firmar(payload: dict) -> str:
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def _encabezado(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
