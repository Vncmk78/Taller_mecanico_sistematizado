"""Diagnóstico de disponibilidad por servicio (Semana 7, decisión R5).

`GET /api/health/servicios/{servicio}` comprueba por separado el proceso
(`/health`), la base (`/health/db`) y, en MS4, el almacenamiento
(`/health/storage`) de un microservicio, y devuelve el estado de cada
comprobación con su latencia, el timeout que la Gateway aplica al servicio y
sus prefijos. Los microservicios se simulan con `respx`.
"""
from __future__ import annotations

from datetime import datetime

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import gateway.cliente_http as cliente_http
from gateway.config import settings
from gateway.main import app
from gateway.rutas import MICROSERVICIOS, MICROSERVICIOS_POR_NOMBRE

_NOMBRES = [s.nombre for s in MICROSERVICIOS]


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


@pytest.fixture
def api_mock() -> respx.MockRouter:
    with respx.mock(assert_all_mocked=True) as mock:
        yield mock


@pytest.fixture(autouse=True)
def cliente_http_sin_estado() -> None:
    yield
    cliente_http.reset_cliente()


def _url(nombre: str, camino: str) -> str:
    return f"{MICROSERVICIOS_POR_NOMBRE[nombre].url}{camino}"


def _mockar(api_mock: respx.MockRouter, nombre: str, **por_comprobacion) -> None:
    """Simula cada comprobación del servicio: Response o excepción (por defecto 200)."""
    for comprobacion, camino in MICROSERVICIOS_POR_NOMBRE[nombre].comprobaciones:
        resultado = por_comprobacion.get(comprobacion, httpx.Response(200, json={"status": "ok"}))
        ruta = api_mock.get(_url(nombre, camino))
        if isinstance(resultado, Exception):
            ruta.mock(side_effect=resultado)
        else:
            ruta.mock(return_value=resultado)


def _sin_urls_internas(texto: str) -> None:
    assert "http://" not in texto
    assert "localhost" not in texto
    for servicio in MICROSERVICIOS:
        assert servicio.url not in texto


@pytest.mark.parametrize("nombre", _NOMBRES)
def test_servicio_sano_responde_200_ok(gateway: TestClient, api_mock, nombre: str) -> None:
    _mockar(api_mock, nombre)

    respuesta = gateway.get(f"/api/health/servicios/{nombre}")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["servicio"] == nombre
    assert cuerpo["estado"] == "ok"
    esperadas = {c for c, _ in MICROSERVICIOS_POR_NOMBRE[nombre].comprobaciones}
    assert set(cuerpo["comprobaciones"]) == esperadas
    for resultado in cuerpo["comprobaciones"].values():
        assert resultado["estado"] == "ok"
        assert isinstance(resultado["latencia_ms"], int)
    assert cuerpo["prefijos"] == sorted(
        f"/api/{p}" for p in MICROSERVICIOS_POR_NOMBRE[nombre].todos_los_prefijos
    )
    assert cuerpo["timeouts"]["health"] == settings.HEALTH_TIMEOUT_SECONDS
    datetime.fromisoformat(cuerpo["comprobado_en"])
    assert respuesta.headers["cache-control"] == "no-store"
    _sin_urls_internas(respuesta.text)


def test_solo_ms4_comprueba_almacenamiento() -> None:
    for servicio in MICROSERVICIOS:
        nombres = [c for c, _ in servicio.comprobaciones]
        assert nombres[:2] == ["proceso", "base"]
        assert ("almacenamiento" in nombres) == (servicio.nombre == "ms4_evidencias")


def test_base_caida_con_proceso_vivo_es_degradado(gateway: TestClient, api_mock) -> None:
    _mockar(api_mock, "ms3_presupuestos", base=httpx.Response(500, text="Internal Server Error"))

    respuesta = gateway.get("/api/health/servicios/ms3_presupuestos")

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "degradado"
    assert cuerpo["comprobaciones"]["proceso"]["estado"] == "ok"
    assert cuerpo["comprobaciones"]["base"] == {
        "estado": "error",
        "latencia_ms": cuerpo["comprobaciones"]["base"]["latencia_ms"],
        "codigo_http": 500,
    }


def test_ms4_sin_almacenamiento_es_degradado(gateway: TestClient, api_mock) -> None:
    _mockar(
        api_mock,
        "ms4_evidencias",
        almacenamiento=httpx.Response(503, json={"detail": "El almacenamiento no está disponible"}),
    )

    respuesta = gateway.get("/api/health/servicios/ms4_evidencias")

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "degradado"
    assert cuerpo["comprobaciones"]["base"]["estado"] == "ok"
    assert cuerpo["comprobaciones"]["almacenamiento"]["codigo_http"] == 503


@pytest.mark.parametrize(
    "excepcion,estado",
    [
        (httpx.ConnectError("rechazada"), "caido"),
        (httpx.ReadTimeout("lento"), "tiempo_agotado"),
    ],
)
def test_proceso_sin_respuesta_es_caido(
    gateway: TestClient, api_mock, excepcion: Exception, estado: str
) -> None:
    _mockar(api_mock, "ms2_taller", proceso=excepcion, base=excepcion)

    respuesta = gateway.get("/api/health/servicios/ms2_taller")

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "caido"
    assert cuerpo["comprobaciones"]["proceso"] == {"estado": estado}
    _sin_urls_internas(respuesta.text)


def test_timeouts_reportados_son_los_que_aplica_la_gateway(
    gateway: TestClient, api_mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MS1_TIMEOUT_SECONDS", 10.0)
    _mockar(api_mock, "ms1_auth")

    timeouts = gateway.get("/api/health/servicios/ms1_auth").json()["timeouts"]

    assert timeouts == {
        "conexion": settings.TIMEOUT_CONNECT_SECONDS,
        "lectura": 10.0,
        "escritura": 10.0,
        "health": settings.HEALTH_TIMEOUT_SECONDS,
    }


def test_cada_comprobacion_se_consulta_una_vez(gateway: TestClient, api_mock) -> None:
    _mockar(api_mock, "ms4_evidencias")

    gateway.get("/api/health/servicios/ms4_evidencias")

    assert len(api_mock.calls) == 3
    caminos = sorted(llamada.request.url.path for llamada in api_mock.calls)
    assert caminos == ["/health", "/health/db", "/health/storage"]


def test_nombre_ignora_mayusculas(gateway: TestClient, api_mock) -> None:
    _mockar(api_mock, "ms1_auth")
    assert gateway.get("/api/health/servicios/MS1_AUTH").json()["servicio"] == "ms1_auth"


def test_servicio_desconocido_responde_404_de_la_gateway(gateway: TestClient, api_mock) -> None:
    respuesta = gateway.get("/api/health/servicios/ms9_facturas")

    assert respuesta.status_code == 404
    cuerpo = respuesta.json()
    assert cuerpo["error"]["codigo"] == "RUTA_NO_ENCONTRADA"
    assert "ms1_auth" in cuerpo["detail"]
    # No consulta a nadie ni se reenvía al proxy.
    assert len(api_mock.calls) == 0


def test_el_agregado_no_cambia(gateway: TestClient, api_mock) -> None:
    """`/api/health/servicios` sigue consultando solo `/health/db` de cada uno."""
    for servicio in MICROSERVICIOS:
        api_mock.get(_url(servicio.nombre, "/health/db")).mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

    respuesta = gateway.get("/api/health/servicios")

    assert respuesta.status_code == 200
    assert set(respuesta.json()["servicios"]) == set(_NOMBRES)
    assert len(api_mock.calls) == 4


def test_openapi_documenta_el_diagnostico(gateway: TestClient) -> None:
    app.openapi_schema = None
    try:
        operacion = gateway.get("/openapi.json").json()["paths"][
            "/api/health/servicios/{servicio}"
        ]["get"]
    finally:
        app.openapi_schema = None
    parametro = next(p for p in operacion["parameters"] if p["name"] == "servicio")
    assert parametro["schema"]["enum"] == _NOMBRES
    assert "diagnostico_ok" in operacion["responses"]["200"]["content"]["application/json"]["examples"]
    assert {"diagnostico_degradado", "diagnostico_caido"} <= set(
        operacion["responses"]["503"]["content"]["application/json"]["examples"]
    )
    assert "security" not in operacion
