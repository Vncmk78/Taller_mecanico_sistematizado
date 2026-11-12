"""Smoke tests de todos los prefijos de la Gateway, en proceso (Semana 7).

Ejecuta `scripts/smoke_prefijos_gateway.py` (el mismo código que se corre
contra un entorno levantado) contra la Gateway REAL conectada a los CUATRO
microservicios REALES mediante `ASGITransport`, cada uno con su base SQLite en
memoria. Así cada smoke test corre también en CI, sin red ni Docker:

* salud de la Gateway, salud agregada y diagnóstico por servicio;
* cada prefijo publicado sin token -> 401 del microservicio;
* cada alias -> 404 del microservicio; prefijo inexistente -> 404 de la Gateway;
* login real (MS1 emite, el resto valida) y cada prefijo con token.

Las dos dependencias externas que no existen en proceso se sustituyen: el
almacenamiento de MS4 (MinIO) y la consulta síncrona MS4 -> MS2 por HTTP.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import gateway.routers.health as routers_health
import gateway.routers.proxy as routers_proxy
import services.ms1_auth.models  # noqa: F401
import services.ms2_taller.models  # noqa: F401
import services.ms3_presupuestos.models  # noqa: F401
import services.ms4_evidencias.main as ms4_main
import services.ms4_evidencias.models  # noqa: F401
from gateway.main import app as gateway_app
from gateway.rutas import MICROSERVICIOS
from services.ms1_auth.config import settings as ms1_settings
from services.ms1_auth.db import Base as BaseMS1
from services.ms1_auth.db import get_db as get_db_ms1
from services.ms1_auth.main import app as app_ms1
from services.ms1_auth.models import Rol
from services.ms2_taller.config import settings as ms2_settings
from services.ms2_taller.db import Base as BaseMS2
from services.ms2_taller.db import get_db as get_db_ms2
from services.ms2_taller.main import app as app_ms2
from services.ms2_taller.models.estado_orden import ESTADOS_ORDEN, EstadoOrden
from services.ms3_presupuestos.config import settings as ms3_settings
from services.ms3_presupuestos.db import Base as BaseMS3
from services.ms3_presupuestos.db import get_db as get_db_ms3
from services.ms3_presupuestos.main import app as app_ms3
from services.ms4_evidencias.config import settings as ms4_settings
from services.ms4_evidencias.db import Base as BaseMS4
from services.ms4_evidencias.db import get_db as get_db_ms4
from services.ms4_evidencias.main import app as app_ms4
from shared.auth import NombreRol

_RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "smoke_prefijos_gateway", _RAIZ / "scripts" / "smoke_prefijos_gateway.py"
)
smoke = importlib.util.module_from_spec(_spec)
sys.modules["smoke_prefijos_gateway"] = smoke
_spec.loader.exec_module(smoke)

_FUNCIONES_SQLITE = [
    ("btrim", 1, lambda valor: valor.strip() if valor is not None else None),
    ("char_length", 1, lambda valor: len(valor) if valor is not None else None),
]

_CLIENTE = ("smoke@pruebas.cl", "ClaveSmoke123!", "Cliente Smoke")


def _sqlite(base):
    motor = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(motor, "connect")
    def _funciones(conexion, _registro) -> None:
        for nombre, aridad, funcion in _FUNCIONES_SQLITE:
            conexion.create_function(nombre, aridad, funcion)

    base.metadata.create_all(motor)
    return motor, sessionmaker(bind=motor, expire_on_commit=False)()


def _override(sesion):
    def reemplazar_db():
        yield sesion

    return reemplazar_db


def _montaje(url: str) -> str:
    partes = urlsplit(url)
    return f"{partes.scheme}://{partes.netloc}"


@pytest.fixture
def gateway_con_microservicios(monkeypatch: pytest.MonkeyPatch):
    bases = [BaseMS1, BaseMS2, BaseMS3, BaseMS4]
    apps = [app_ms1, app_ms2, app_ms3, app_ms4]
    get_dbs = [get_db_ms1, get_db_ms2, get_db_ms3, get_db_ms4]
    creados = [_sqlite(base) for base in bases]

    sesion_ms1, sesion_ms2 = creados[0][1], creados[1][1]
    sesion_ms1.add_all([Rol(nombre=rol.value) for rol in NombreRol])
    sesion_ms1.commit()
    sesion_ms2.add_all(
        [EstadoOrden(estado_codigo=c, nombre=n) for c, n in ESTADOS_ORDEN.items()]
    )
    sesion_ms2.commit()

    for app, get_db, (_, sesion) in zip(apps, get_dbs, creados):
        app.dependency_overrides[get_db] = _override(sesion)

    clave = ms1_settings.JWT_SECRET_KEY
    for configuracion in (ms2_settings, ms3_settings, ms4_settings):
        monkeypatch.setattr(configuracion, "JWT_SECRET_KEY", clave)

    # MinIO no existe en proceso: el bucket "responde".
    monkeypatch.setattr(ms4_main, "crear_cliente_s3", lambda _settings: object())
    monkeypatch.setattr(ms4_main, "verificar_bucket", lambda _cliente, _bucket: True)
    # MS4 -> MS2 es una llamada síncrona por HTTP: la orden 1 no existe.
    import services.ms4_evidencias.integracion_ms2 as ms4_ms2

    monkeypatch.setattr(
        ms4_ms2.httpx,
        "get",
        lambda *a, **k: httpx.Response(404, json={"detail": "Orden no encontrada"}),
    )

    cliente_interno: httpx.AsyncClient | None = None

    def _obtener_cliente() -> httpx.AsyncClient:
        nonlocal cliente_interno
        if cliente_interno is None:
            cliente_interno = httpx.AsyncClient(
                mounts={
                    _montaje(servicio.url): httpx.ASGITransport(app=app)
                    for servicio, app in zip(MICROSERVICIOS, apps)
                }
            )
        return cliente_interno

    monkeypatch.setattr(routers_proxy, "obtener_cliente", _obtener_cliente)
    monkeypatch.setattr(routers_health, "obtener_cliente", _obtener_cliente)

    try:
        with TestClient(gateway_app) as gw:
            yield gw
    finally:
        for app in apps:
            app.dependency_overrides.clear()
        for (motor, sesion), base in zip(creados, bases):
            sesion.close()
            base.metadata.drop_all(motor)
            motor.dispose()


def _fallas(resultados) -> list:
    return [r for r in resultados if r.estado != smoke.PASA]


def test_representativos_cubren_todos_los_prefijos_publicados() -> None:
    publicados = {p for s in MICROSERVICIOS for p in s.prefijos}
    assert set(smoke.REPRESENTATIVOS) == publicados


def test_smoke_sin_token_pasa_en_todos_los_prefijos(gateway_con_microservicios) -> None:
    resultados = smoke.ejecutar(gateway_con_microservicios)

    assert _fallas(resultados) == []
    pruebas = {r.prueba for r in resultados}
    for servicio in MICROSERVICIOS:
        assert f"GET /api/health/servicios/{servicio.nombre}" in pruebas
        for alias in servicio.alias:
            assert f"GET /api/{alias} (alias)" in pruebas
    sin_token = [r for r in resultados if r.prueba.endswith("sin token")]
    assert len(sin_token) == len(smoke.REPRESENTATIVOS)
    assert all(r.obtenido == "401" for r in sin_token)


def test_smoke_con_token_llega_a_cada_microservicio(gateway_con_microservicios) -> None:
    gw = gateway_con_microservicios
    correo, clave, nombre = _CLIENTE
    registro = gw.post(
        "/api/auth/register",
        json={"email": correo, "password": clave, "full_name": nombre},
    )
    assert registro.status_code == 201, registro.text

    resultados = smoke.ejecutar(gw, email=correo, password=clave)

    assert _fallas(resultados) == []
    con_token = {r.prueba: r.obtenido for r in resultados if r.prueba.endswith("con token")}
    assert len(con_token) == len(smoke.REPRESENTATIVOS)
    assert con_token["GET /api/auth/me con token"] == "200"
    # Un Cliente no administra el catálogo de MS3: 403 del propio MS3.
    assert con_token["GET /api/repuestos con token"] == "403"


def test_smoke_detecta_un_microservicio_caido(
    gateway_con_microservicios, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si MS3 no responde, el smoke lo reporta como FALLA (no lo oculta)."""

    class _Caido(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("apagado", request=request)

    apps = [app_ms1, app_ms2, None, app_ms4]  # MS3 apagado
    cliente = httpx.AsyncClient(
        mounts={
            _montaje(servicio.url): (
                httpx.ASGITransport(app=app) if app is not None else _Caido()
            )
            for servicio, app in zip(MICROSERVICIOS, apps)
        }
    )
    monkeypatch.setattr(routers_proxy, "obtener_cliente", lambda: cliente)
    monkeypatch.setattr(routers_health, "obtener_cliente", lambda: cliente)

    resultados = smoke.ejecutar(gateway_con_microservicios)

    fallas = {r.prueba: r for r in _fallas(resultados)}
    assert fallas["GET /api/repuestos sin token"].obtenido == "502 MICROSERVICIO_INALCANZABLE"
    assert fallas["GET /api/health/servicios"].obtenido == "503"
    assert fallas["GET /api/health/servicios/ms3_presupuestos"].obtenido == "503"
    # Solo falla lo que depende de MS3 (y la salud agregada que lo incluye).
    assert {r.servicio for r in fallas.values()} == {"ms3_presupuestos", "los cuatro"}
