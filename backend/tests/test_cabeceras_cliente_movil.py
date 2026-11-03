"""Regresión: cabeceras que necesita un cliente móvil o externo (Semana 9).

Origen: `docs/estudio-consumo-api-movil-redes-externas.md` (hallazgo H-01).
La Gateway reenviaba `Retry-After` (429 del login, 502/503/504 propios), pero
CORS solo exponía `X-Request-ID`. Un cliente que corre en navegador (frontend
web, build web de la app móvil o Expo Web) recibía la cabecera y `fetch()` la
ocultaba: no podía saber cuánto esperar antes de reintentar.

Un cliente nativo (Android/iOS) no envía `Origin` y no pasa por CORS: estas
pruebas verifican también que a él la cabecera le llega igual.
"""
from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import gateway.cliente_http as cliente_http
from gateway.config import settings
from gateway.main import app

ORIGEN_WEB = settings.CORS_ORIGINS[0]
CUERPO_LOGIN = {"email": "cliente@taller.cl", "password": "incorrecta"}


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


def _expuestas(respuesta: httpx.Response) -> set[str]:
    valor = respuesta.headers.get("access-control-expose-headers", "")
    return {cabecera.strip().lower() for cabecera in valor.split(",") if cabecera}


def _login_bloqueado(api_mock: respx.MockRouter) -> None:
    api_mock.post(f"{settings.MS1_URL}/auth/login").mock(
        return_value=httpx.Response(
            429,
            json={"detail": "Demasiados intentos fallidos. Intenta más tarde."},
            headers={"Retry-After": "120"},
        )
    )


def test_429_login_expone_retry_after_al_navegador(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    _login_bloqueado(api_mock)

    respuesta = gateway.post(
        "/api/auth/login", json=CUERPO_LOGIN, headers={"Origin": ORIGEN_WEB}
    )

    assert respuesta.status_code == 429
    assert respuesta.headers["retry-after"] == "120"
    assert respuesta.headers["access-control-allow-origin"] == ORIGEN_WEB
    assert "retry-after" in _expuestas(respuesta)


def test_502_de_la_gateway_expone_retry_after_al_navegador(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.get(f"{settings.MS2_URL}/ordenes").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    respuesta = gateway.get("/api/ordenes", headers={"Origin": ORIGEN_WEB})

    assert respuesta.status_code == 502
    assert respuesta.headers["retry-after"] == str(settings.RETRY_AFTER_SECONDS)
    assert {"retry-after", "x-request-id"} <= _expuestas(respuesta)


def test_cliente_nativo_sin_origin_recibe_retry_after_sin_cors(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    _login_bloqueado(api_mock)

    respuesta = gateway.post("/api/auth/login", json=CUERPO_LOGIN)

    assert respuesta.status_code == 429
    assert respuesta.headers["retry-after"] == "120"
    assert respuesta.headers["x-request-id"]
    # Sin Origin no hay CORS: la app nativa no depende de la lista de orígenes.
    assert "access-control-allow-origin" not in respuesta.headers


def test_preflight_de_la_app_permite_authorization_y_request_id(
    gateway: TestClient,
) -> None:
    respuesta = gateway.options(
        "/api/ordenes",
        headers={
            "Origin": ORIGEN_WEB,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization, x-request-id",
        },
    )

    assert respuesta.status_code == 200
    permitidas = respuesta.headers["access-control-allow-headers"].lower()
    assert "authorization" in permitidas
    assert "x-request-id" in permitidas
