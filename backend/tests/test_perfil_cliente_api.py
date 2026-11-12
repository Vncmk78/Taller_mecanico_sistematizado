"""Pruebas HTTP de la preparación del perfil Cliente local en MS2.

Cubre `POST /clientes/perfil` (preparación idempotente) y `GET /clientes/perfil`
(consulta sin efectos). La identidad siempre se toma del JWT.

La concurrencia real contra la restricción única de PostgreSQL se verifica en
`test_perfil_cliente_postgresql.py`; aquí se simula la carrera perdida.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import services.ms2_taller.services.clientes as servicio_clientes
from services.ms2_taller.config import settings
from services.ms2_taller.db import get_db
from services.ms2_taller.main import app
from services.ms2_taller.models import Base, Cliente, EstadoOrden
from services.ms2_taller.models.estado_orden import ESTADOS_ORDEN
from shared.auth import NombreRol, crear_token_acceso

RUTA = "/clientes/perfil"


@pytest.fixture
def db_ms2() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def registrar_funciones_sqlite(conexion, _registro) -> None:
        conexion.create_function(
            "btrim", 1, lambda valor: valor.strip() if valor is not None else None
        )

    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine, expire_on_commit=False)()
    sesion.add_all(
        [EstadoOrden(estado_codigo=c, nombre=n) for c, n in ESTADOS_ORDEN.items()]
    )
    sesion.commit()
    try:
        yield sesion
    finally:
        sesion.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def api(db_ms2: Session) -> Generator[TestClient, None, None]:
    def reemplazar_db():
        yield db_ms2

    app.dependency_overrides[get_db] = reemplazar_db
    with TestClient(app) as cliente_http:
        yield cliente_http
    app.dependency_overrides.clear()


def _headers(usuario_id: int, *roles: NombreRol) -> dict[str, str]:
    token = crear_token_acceso(
        usuario_id,
        list(roles) or [NombreRol.CLIENTE],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
        minutos_expiracion=5,
    )
    return {"Authorization": f"Bearer {token}"}


def _perfiles(db: Session) -> list[Cliente]:
    db.expire_all()
    return list(db.scalars(select(Cliente).order_by(Cliente.cliente_id)))


# ── autenticación y autorización ────────────────────────────────────────────


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_sin_token_devuelve_401(api: TestClient, db_ms2: Session, metodo: str):
    respuesta = api.request(metodo, RUTA, json={} if metodo == "post" else None)

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
    assert _perfiles(db_ms2) == []


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_token_invalido_devuelve_401(api: TestClient, db_ms2: Session, metodo: str):
    respuesta = api.request(
        metodo,
        RUTA,
        json={} if metodo == "post" else None,
        headers={"Authorization": "Bearer token-invalido"},
    )

    assert respuesta.status_code == 401
    assert _perfiles(db_ms2) == []


@pytest.mark.parametrize(
    "roles", [(NombreRol.MECANICO,), (NombreRol.ADMINISTRADOR,),
              (NombreRol.MECANICO, NombreRol.ADMINISTRADOR)],
)
def test_sin_rol_cliente_devuelve_403_y_no_crea_perfil(
    api: TestClient, db_ms2: Session, roles
):
    preparar = api.post(RUTA, json={}, headers=_headers(10, *roles))
    consultar = api.get(RUTA, headers=_headers(10, *roles))

    assert preparar.status_code == 403
    assert consultar.status_code == 403
    assert _perfiles(db_ms2) == []


@pytest.mark.parametrize(
    "body",
    [
        {"usuario_id": 99},
        {"cliente_id": 1},
        {"roles": ["cliente"]},
        {"telefono": "+56911111111", "usuario_id": 99},
    ],
)
def test_body_no_admite_identidad_ni_roles(api: TestClient, db_ms2: Session, body):
    respuesta = api.post(RUTA, json=body, headers=_headers(10))

    assert respuesta.status_code == 422
    assert _perfiles(db_ms2) == []


@pytest.mark.parametrize("telefono", ["", "   ", "1" * 31])
def test_telefono_invalido_devuelve_422(api: TestClient, db_ms2: Session, telefono):
    respuesta = api.post(RUTA, json={"telefono": telefono}, headers=_headers(10))

    assert respuesta.status_code == 422
    assert _perfiles(db_ms2) == []


# ── preparación ─────────────────────────────────────────────────────────────


def test_primera_preparacion_crea_perfil_del_usuario_del_jwt(
    api: TestClient, db_ms2: Session
):
    respuesta = api.post(RUTA, json={}, headers=_headers(10))

    assert respuesta.status_code == 201
    perfiles = _perfiles(db_ms2)
    assert len(perfiles) == 1
    assert respuesta.json() == {
        "cliente_id": perfiles[0].cliente_id,
        "usuario_id": 10,
        "telefono": None,
    }


def test_cliente_multirol_puede_preparar_su_perfil(api: TestClient, db_ms2: Session):
    respuesta = api.post(
        RUTA, json={}, headers=_headers(11, NombreRol.CLIENTE, NombreRol.MECANICO)
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["usuario_id"] == 11


def test_repetir_preparacion_devuelve_200_sin_duplicar(
    api: TestClient, db_ms2: Session
):
    primera = api.post(RUTA, json={"telefono": " +56 9 1234 5678 "}, headers=_headers(10))
    repetida = api.post(RUTA, json={"telefono": "+56 9 1234 5678"}, headers=_headers(10))
    sin_telefono = api.post(RUTA, json={}, headers=_headers(10))

    assert primera.status_code == 201
    assert primera.json()["telefono"] == "+56 9 1234 5678"
    assert repetida.status_code == 200
    assert sin_telefono.status_code == 200
    assert repetida.json() == primera.json() == sin_telefono.json()
    assert len(_perfiles(db_ms2)) == 1


def test_perfil_existente_no_se_sobrescribe_con_otro_telefono(
    api: TestClient, db_ms2: Session
):
    db_ms2.add(Cliente(usuario_id=10, telefono="+56911111111"))
    db_ms2.commit()

    respuesta = api.post(RUTA, json={"telefono": "+56922222222"}, headers=_headers(10))

    assert respuesta.status_code == 409
    assert "no se modificó" in respuesta.json()["detail"]
    perfiles = _perfiles(db_ms2)
    assert [(p.usuario_id, p.telefono) for p in perfiles] == [(10, "+56911111111")]


def test_perfil_creado_por_semilla_se_reconoce_como_existente(
    api: TestClient, db_ms2: Session
):
    db_ms2.add(Cliente(usuario_id=10, telefono=None))
    db_ms2.commit()

    respuesta = api.post(RUTA, json={}, headers=_headers(10))

    assert respuesta.status_code == 200
    assert len(_perfiles(db_ms2)) == 1


def test_cada_usuario_prepara_solo_su_propio_perfil(api: TestClient, db_ms2: Session):
    assert api.post(RUTA, json={}, headers=_headers(10)).status_code == 201
    assert api.post(RUTA, json={}, headers=_headers(20)).status_code == 201

    assert api.get(RUTA, headers=_headers(10)).json()["usuario_id"] == 10
    assert api.get(RUTA, headers=_headers(20)).json()["usuario_id"] == 20
    assert [p.usuario_id for p in _perfiles(db_ms2)] == [10, 20]


def test_carrera_perdida_recupera_el_perfil_ganador(
    api: TestClient, db_ms2: Session, monkeypatch: pytest.MonkeyPatch
):
    """Otro proceso crea el perfil entre la búsqueda y la inserción."""

    crear_original = servicio_clientes.crear_cliente

    def crear_tras_ganador(db, usuario_id, telefono=None):
        # El "otro proceso" confirma primero; luego esta llamada choca con la
        # restricción única y `asegurar_cliente` recupera el perfil ganador.
        crear_original(db, usuario_id, telefono)
        raise servicio_clientes.ClienteDuplicadoError("carrera simulada")

    monkeypatch.setattr(servicio_clientes, "crear_cliente", crear_tras_ganador)

    respuesta = api.post(RUTA, json={}, headers=_headers(10))

    assert respuesta.status_code == 201
    perfiles = _perfiles(db_ms2)
    assert len(perfiles) == 1
    assert respuesta.json()["cliente_id"] == perfiles[0].cliente_id


def test_fallo_de_persistencia_responde_500_y_permite_reintentar(
    api: TestClient, db_ms2: Session, monkeypatch: pytest.MonkeyPatch
):
    commit_original = db_ms2.commit

    def commit_fallido():
        raise SQLAlchemyError("base no disponible")

    monkeypatch.setattr(db_ms2, "commit", commit_fallido)
    fallida = api.post(RUTA, json={}, headers=_headers(10))

    assert fallida.status_code == 500
    assert fallida.json() == {"detail": "No fue posible preparar el perfil de cliente"}
    monkeypatch.setattr(db_ms2, "commit", commit_original)
    assert _perfiles(db_ms2) == []

    reintento = api.post(RUTA, json={}, headers=_headers(10))

    assert reintento.status_code == 201
    assert len(_perfiles(db_ms2)) == 1


# ── consulta y relación con vehículos ───────────────────────────────────────


def test_consultar_sin_perfil_devuelve_404_y_no_lo_crea(
    api: TestClient, db_ms2: Session
):
    respuesta = api.get(RUTA, headers=_headers(10))
    vehiculos = api.get("/vehiculos", headers=_headers(10))

    assert respuesta.status_code == 404
    # La consulta de vehículos conserva su comportamiento: tampoco crea.
    assert vehiculos.status_code == 404
    assert db_ms2.scalar(select(func.count()).select_from(Cliente)) == 0


def test_preparar_habilita_el_registro_de_vehiculos(api: TestClient, db_ms2: Session):
    vehiculo = {"patente": "PERF01", "marca": "Toyota", "modelo": "Yaris"}
    antes = api.post("/vehiculos", json=vehiculo, headers=_headers(10))
    assert antes.status_code == 404

    perfil = api.post(RUTA, json={}, headers=_headers(10))
    consulta = api.get(RUTA, headers=_headers(10))
    despues = api.post("/vehiculos", json=vehiculo, headers=_headers(10))

    assert perfil.status_code == 201
    assert consulta.status_code == 200
    assert consulta.json() == perfil.json()
    assert despues.status_code == 201
    assert despues.json()["cliente_id"] == perfil.json()["cliente_id"]
    assert api.get("/vehiculos", headers=_headers(10)).json()[0]["patente"] == "PERF01"
