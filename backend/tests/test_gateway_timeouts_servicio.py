"""Timeouts por servicio y respuestas estandarizadas de la Gateway (Semana 7).

Decisiones R1 a R4 de `docs/estudio-resiliencia-timeouts-retries.md`:

* R1: `GATEWAY_MS<n>_TIMEOUT_SECONDS` fija read/write del servicio destino;
  sin definirlo rigen los generales (y 60 s para `evidencias`).
* R3: los errores de la Gateway salen con `Cache-Control: no-store` y los 502,
  503 y 504 además con `Retry-After`.
* R4: el log de un fallo de red nombra el servicio y el timeout, sin URL
  interna.
"""
from __future__ import annotations

import logging

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import ValidationError

import gateway.cliente_http as cliente_http
from gateway.cliente_http import timeout_para, timeout_servicio
from gateway.config import GatewaySettings, settings
from gateway.errores import (
    GATEWAY_SATURADA,
    MICROSERVICIO_INALCANZABLE,
    TIEMPO_AGOTADO,
)
from gateway.main import app
from gateway.rutas import MICROSERVICIOS

_VARIABLES = {
    "ms1_auth": "MS1_TIMEOUT_SECONDS",
    "ms2_taller": "MS2_TIMEOUT_SECONDS",
    "ms3_presupuestos": "MS3_TIMEOUT_SECONDS",
    "ms4_evidencias": "MS4_TIMEOUT_SECONDS",
}

# Un prefijo publicado y una ruta de ejemplo por servicio.
_RUTA_POR_SERVICIO = {
    "ms1_auth": ("auth", "/auth/me", settings.MS1_URL),
    "ms2_taller": ("vehiculos", "/vehiculos", settings.MS2_URL),
    "ms3_presupuestos": ("repuestos", "/repuestos", settings.MS3_URL),
    "ms4_evidencias": ("evidencias", "/evidencias", settings.MS4_URL),
}


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def sin_timeouts_propios(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada test parte sin timeouts por servicio y sin cliente compartido."""
    for variable in _VARIABLES.values():
        monkeypatch.setattr(settings, variable, None)
    yield
    cliente_http.reset_cliente()


# ------------------------------------------------------------ configuración --


def test_cada_servicio_del_catalogo_tiene_su_variable() -> None:
    assert {s.nombre: s.variable_timeout for s in MICROSERVICIOS} == _VARIABLES


def test_por_defecto_no_hay_timeouts_propios() -> None:
    configuracion = GatewaySettings(_env_file=None)
    for variable in _VARIABLES.values():
        assert getattr(configuracion, variable) is None
    assert configuracion.RETRY_AFTER_SECONDS == 5


def test_timeouts_se_leen_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_MS1_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("GATEWAY_MS3_TIMEOUT_SECONDS", "20.5")
    monkeypatch.setenv("GATEWAY_RETRY_AFTER_SECONDS", "8")
    configuracion = GatewaySettings(_env_file=None)
    assert configuracion.MS1_TIMEOUT_SECONDS == 10.0
    assert configuracion.MS3_TIMEOUT_SECONDS == 20.5
    assert configuracion.MS2_TIMEOUT_SECONDS is None
    assert configuracion.RETRY_AFTER_SECONDS == 8


@pytest.mark.parametrize("valor", ["0", "-1", "301", "abc"])
def test_timeout_de_servicio_invalido_se_rechaza(
    monkeypatch: pytest.MonkeyPatch, valor: str
) -> None:
    monkeypatch.setenv("GATEWAY_MS2_TIMEOUT_SECONDS", valor)
    with pytest.raises(ValidationError):
        GatewaySettings(_env_file=None)


# ---------------------------------------------------------- timeout_para --


def test_sin_timeout_propio_rigen_los_generales() -> None:
    for prefijo in ("auth", "vehiculos", "presupuestos", "repuestos"):
        timeout = timeout_para(prefijo)
        assert timeout.read == settings.TIMEOUT_READ_SECONDS
        assert timeout.write == settings.TIMEOUT_WRITE_SECONDS
    assert timeout_para("evidencias").read == settings.TIMEOUT_ARCHIVOS_SECONDS


@pytest.mark.parametrize("servicio", list(_VARIABLES))
def test_timeout_propio_se_aplica_a_todos_sus_prefijos(
    monkeypatch: pytest.MonkeyPatch, servicio: str
) -> None:
    monkeypatch.setattr(settings, _VARIABLES[servicio], 7.5)
    destino = next(s for s in MICROSERVICIOS if s.nombre == servicio)
    for prefijo in destino.todos_los_prefijos:
        timeout = timeout_para(prefijo)
        assert timeout.read == 7.5, prefijo
        assert timeout.write == 7.5, prefijo
        # connect y pool no dependen del servicio.
        assert timeout.connect == settings.TIMEOUT_CONNECT_SECONDS
        assert timeout.pool == settings.TIMEOUT_POOL_SECONDS
        assert timeout_servicio(prefijo) == 7.5
    # Los demás servicios no se ven afectados.
    for otro in MICROSERVICIOS:
        if otro.nombre != servicio:
            assert timeout_servicio(otro.prefijos[0]) is None


def test_timeout_de_ms4_tiene_prioridad_sobre_el_de_archivos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MS4_TIMEOUT_SECONDS", 90.0)
    assert timeout_para("evidencias").read == 90.0
    assert timeout_para("evidencias").write == 90.0


def test_prefijo_desconocido_usa_los_generales() -> None:
    assert timeout_servicio("facturas") is None
    assert timeout_para("facturas").read == settings.TIMEOUT_READ_SECONDS


@pytest.mark.parametrize("servicio", list(_RUTA_POR_SERVICIO))
def test_el_proxy_envia_con_el_timeout_del_servicio(
    gateway: TestClient, monkeypatch: pytest.MonkeyPatch, servicio: str
) -> None:
    monkeypatch.setattr(settings, _VARIABLES[servicio], 4.0)
    _, ruta, base = _RUTA_POR_SERVICIO[servicio]
    with respx.mock(assert_all_mocked=True) as mock:
        llamada = mock.get(f"{base}{ruta}").mock(
            return_value=httpx.Response(200, json=[])
        )
        respuesta = gateway.get(f"/api{ruta}")
    assert respuesta.status_code == 200
    aplicado = llamada.calls.last.request.extensions["timeout"]
    assert aplicado["read"] == 4.0
    assert aplicado["write"] == 4.0
    assert aplicado["connect"] == settings.TIMEOUT_CONNECT_SECONDS


# ------------------------------------------------- respuestas estandarizadas --


@pytest.mark.parametrize(
    "excepcion,estado,codigo",
    [
        (httpx.ConnectError("rechazada"), 502, MICROSERVICIO_INALCANZABLE),
        (httpx.ConnectTimeout("lento al conectar"), 502, MICROSERVICIO_INALCANZABLE),
        (httpx.ReadTimeout("lento al responder"), 504, TIEMPO_AGOTADO),
        (httpx.WriteTimeout("lento al recibir"), 504, TIEMPO_AGOTADO),
        (httpx.PoolTimeout("sin conexiones"), 503, GATEWAY_SATURADA),
    ],
)
def test_errores_de_disponibilidad_traen_retry_after(
    gateway: TestClient, excepcion: Exception, estado: int, codigo: str
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.get(f"{settings.MS3_URL}/repuestos").mock(side_effect=excepcion)
        respuesta = gateway.get("/api/repuestos", headers={"X-Request-ID": "smoke-1"})
    assert respuesta.status_code == estado
    assert respuesta.headers["retry-after"] == str(settings.RETRY_AFTER_SECONDS)
    assert respuesta.headers["cache-control"] == "no-store"
    assert respuesta.headers["x-request-id"] == "smoke-1"
    cuerpo = respuesta.json()
    assert cuerpo["error"] == {
        "codigo": codigo,
        "estado": estado,
        "ruta": "/api/repuestos",
        "request_id": "smoke-1",
    }
    assert settings.MS3_URL not in respuesta.text


def test_retry_after_es_configurable(
    gateway: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RETRY_AFTER_SECONDS", 30)
    with respx.mock(assert_all_mocked=True) as mock:
        mock.get(f"{settings.MS2_URL}/vehiculos").mock(side_effect=httpx.ReadTimeout("x"))
        respuesta = gateway.get("/api/vehiculos")
    assert respuesta.headers["retry-after"] == "30"


def test_404_de_la_gateway_no_se_cachea_ni_sugiere_reintento(gateway: TestClient) -> None:
    respuesta = gateway.get("/api/facturas")
    assert respuesta.status_code == 404
    assert respuesta.headers["cache-control"] == "no-store"
    assert "retry-after" not in respuesta.headers


def test_error_json_del_microservicio_pasa_sin_cabeceras_agregadas(
    gateway: TestClient,
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.get(f"{settings.MS3_URL}/repuestos").mock(
            return_value=httpx.Response(503, json={"detail": "MS2 no disponible"})
        )
        respuesta = gateway.get("/api/repuestos")
    assert respuesta.status_code == 503
    assert respuesta.json() == {"detail": "MS2 no disponible"}
    assert "retry-after" not in respuesta.headers


def test_log_del_fallo_nombra_servicio_y_timeout_sin_url(
    gateway: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "MS3_TIMEOUT_SECONDS", 12.0)
    with caplog.at_level(logging.WARNING, logger="gateway"):
        with respx.mock(assert_all_mocked=True) as mock:
            mock.get(f"{settings.MS3_URL}/inventario/alertas").mock(
                side_effect=httpx.ReadTimeout("lento")
            )
            gateway.get("/api/inventario/alertas", headers={"X-Request-ID": "log-1"})
    mensajes = [r.getMessage() for r in caplog.records if r.name == "gateway"]
    fallo = next(m for m in mensajes if "Fallo de red" in m)
    assert "ms3_presupuestos" in fallo
    assert "ReadTimeout" in fallo
    assert "timeout_lectura=12.0s" in fallo
    assert "log-1" in fallo
    assert settings.MS3_URL not in fallo
