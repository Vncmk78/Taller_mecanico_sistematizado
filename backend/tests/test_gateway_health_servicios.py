"""Pruebas del health check de servicios de la Gateway (Semana 4, tarea 4).

El endpoint `GET /api/health/servicios` consulta `/health/db` de los cuatro
microservicios en paralelo con el cliente HTTPX compartido y responde el estado
de cada uno. `GET /api/health` sigue siendo solo de la Gateway (no consulta a
nadie) y el índice `/` no expone URLs internas.
"""
from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import gateway.cliente_http as cliente_http
from gateway.config import settings
from gateway.main import app

# Nombre público de cada microservicio -> URL base de su /health/db.
_BASES = {
    "ms1_auth": settings.MS1_URL,
    "ms2_taller": settings.MS2_URL,
    "ms3_presupuestos": settings.MS3_URL,
    "ms4_evidencias": settings.MS4_URL,
}

_SERVICIOS = set(_BASES)


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


@pytest.fixture
def api_mock() -> respx.MockRouter:
    """Mock de `httpx`: cualquier petición sin ruta definida falla sola."""
    with respx.mock(assert_all_mocked=True) as mock:
        yield mock


@pytest.fixture(autouse=True)
def cliente_http_sin_estado() -> None:
    """Descarta el cliente compartido entre tests (mismo criterio que el proxy)."""
    yield
    cliente_http.reset_cliente()


def _url_health(nombre: str) -> str:
    return f"{_BASES[nombre]}/health/db"


def _mockar_ok(api_mock: respx.MockRouter, nombres) -> None:
    for nombre in nombres:
        api_mock.get(_url_health(nombre)).mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )


def _assert_sin_urls_internas(respuesta: httpx.Response) -> None:
    assert "http://" not in respuesta.text
    assert "localhost" not in respuesta.text
    for base in _BASES.values():
        assert base not in respuesta.text


# a) Todos los servicios responden: 200 con todos en "ok".
def test_todos_ok_devuelve_200_y_cuatro_ok(gateway: TestClient, api_mock) -> None:
    _mockar_ok(api_mock, _BASES)

    respuesta = gateway.get("/api/health/servicios")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["gateway"] == "ok"
    assert set(cuerpo["servicios"]) == _SERVICIOS
    for nombre in _BASES:
        estado = cuerpo["servicios"][nombre]
        assert estado["estado"] == "ok"
        assert isinstance(estado["latencia_ms"], int)
        assert estado["latencia_ms"] >= 0


# b) Un servicio caído (ConnectError): 503 degradado y ese en "caido".
def test_ms3_caido_devuelve_503_degradado(gateway: TestClient, api_mock) -> None:
    api_mock.get(_url_health("ms3_presupuestos")).mock(
        side_effect=httpx.ConnectError("ms3 caido")
    )
    _mockar_ok(api_mock, ("ms1_auth", "ms2_taller", "ms4_evidencias"))

    respuesta = gateway.get("/api/health/servicios")
    _assert_sin_urls_internas(respuesta)

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "degradado"
    assert cuerpo["servicios"]["ms3_presupuestos"]["estado"] == "caido"
    for nombre in ("ms1_auth", "ms2_taller", "ms4_evidencias"):
        assert cuerpo["servicios"][nombre]["estado"] == "ok"


# c) Un servicio que no responde a tiempo (ReadTimeout): "tiempo_agotado".
def test_ms2_timeout_devuelve_tiempo_agotado(gateway: TestClient, api_mock) -> None:
    api_mock.get(_url_health("ms2_taller")).mock(
        side_effect=httpx.ReadTimeout("ms2 lento")
    )
    _mockar_ok(api_mock, ("ms1_auth", "ms3_presupuestos", "ms4_evidencias"))

    respuesta = gateway.get("/api/health/servicios")
    _assert_sin_urls_internas(respuesta)

    assert respuesta.status_code == 503
    estado = respuesta.json()["servicios"]["ms2_taller"]
    assert estado == {"estado": "tiempo_agotado"}


# d) Un servicio responde pero con estado distinto de 200: "sin_base".
def test_ms4_503_devuelve_sin_base_con_codigo(gateway: TestClient, api_mock) -> None:
    api_mock.get(_url_health("ms4_evidencias")).mock(
        return_value=httpx.Response(503, json={"status": "error"})
    )
    _mockar_ok(api_mock, ("ms1_auth", "ms2_taller", "ms3_presupuestos"))

    respuesta = gateway.get("/api/health/servicios")

    assert respuesta.status_code == 503
    estado = respuesta.json()["servicios"]["ms4_evidencias"]
    assert estado["estado"] == "sin_base"
    assert estado["codigo_http"] == 503
    assert isinstance(estado["latencia_ms"], int)
    assert estado["latencia_ms"] >= 0


# e) Todos los servicios caídos: 503 y el endpoint no revienta.
def test_todos_caidos_503_y_no_revienta(gateway: TestClient, api_mock) -> None:
    for nombre in _BASES:
        api_mock.get(_url_health(nombre)).mock(
            side_effect=httpx.ConnectError(f"{nombre} caido")
        )

    respuesta = gateway.get("/api/health/servicios")
    _assert_sin_urls_internas(respuesta)

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "degradado"
    for nombre in _BASES:
        assert cuerpo["servicios"][nombre]["estado"] == "caido"


# f) Cabeceras: Cache-Control no-store y X-Request-ID siempre presentes.
def test_cache_control_no_store_y_request_id(gateway: TestClient, api_mock) -> None:
    _mockar_ok(api_mock, _BASES)

    respuesta = gateway.get("/api/health/servicios")

    assert respuesta.headers["cache-control"] == "no-store"
    assert "x-request-id" in respuesta.headers


# g) /api/health responde 200 solo por la Gateway, sin llamar a ningún servicio.
def test_api_health_no_consulta_a_nadie(gateway: TestClient, api_mock) -> None:
    # Sin rutas registradas, cualquier llamada de /api/health a un servicio
    # fallaría por assert_all_mocked; que pase y no haya llamadas prueba que no
    # consulta a nadie.
    respuesta = gateway.get("/api/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok", "servicio": settings.SERVICE_NAME}
    assert api_mock.calls == []


# h) /api/health/servicios no cae en el proxy: responde el JSON de health.
def test_health_servicios_no_se_reenvia_al_proxy(gateway: TestClient, api_mock) -> None:
    _mockar_ok(api_mock, _BASES)

    respuesta = gateway.get("/api/health/servicios")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert "error" not in cuerpo
    assert "servicios" in cuerpo


# i) El índice ya no expone URLs internas de los microservicios.
def test_indice_no_expone_urls_internas(gateway: TestClient) -> None:
    respuesta = gateway.get("/")

    assert respuesta.status_code == 200
    _assert_sin_urls_internas(respuesta)
    cuerpo = respuesta.json()
    assert set(cuerpo["microservicios"]) == _SERVICIOS
    assert "/api/health/servicios" in cuerpo["ejemplos"]


# j) Cada servicio se consulta exactamente una vez (consulta en paralelo).
def test_consulta_cada_servicio_exactamente_una_vez(gateway: TestClient, api_mock) -> None:
    rutas = {
        nombre: api_mock.get(_url_health(nombre)).mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        for nombre in _BASES
    }

    gateway.get("/api/health/servicios")

    for nombre, ruta in rutas.items():
        assert len(ruta.calls) == 1, f"{nombre} se consultó {len(ruta.calls)} veces"