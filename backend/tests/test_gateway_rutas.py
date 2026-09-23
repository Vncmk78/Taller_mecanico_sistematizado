"""Pruebas del enrutamiento de la API Gateway (Semana 1, tarea 2).

Simulan MS1 y MS2 con `respx` (sin levantarlos) para comprobar que la Gateway
reenvía hacia la URL correcta conservando método, body, query string y la
cabecera Authorization, que es donde viaja el JWT hacia el microservicio.
"""
from __future__ import annotations

import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from gateway.config import settings
from gateway.main import app
from gateway.rutas import resolver_microservicio


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


@pytest.fixture
def api_mock() -> respx.MockRouter:
    """Mock de `httpx`: cualquier petición sin ruta definida falla sola."""
    with respx.mock(assert_all_mocked=True) as mock:
        yield mock


def test_auth_login_reenvia_a_ms1_con_su_body(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.post(f"{settings.MS1_URL}/auth/login").mock(
        return_value=httpx.Response(200, json={"token": "abc.def.ghi"})
    )

    respuesta = gateway.post("/api/auth/login", json={"usuario": "admin", "clave": "1234"})

    assert respuesta.status_code == 200
    assert ruta.called
    llamada = ruta.calls.last.request
    assert str(llamada.url) == f"{settings.MS1_URL}/auth/login"
    assert json.loads(llamada.content.decode()) == {"usuario": "admin", "clave": "1234"}


def test_authorization_llega_al_microservicio(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.get(f"{settings.MS1_URL}/auth/me").mock(
        return_value=httpx.Response(200, json={"usuario": "admin"})
    )

    respuesta = gateway.get("/api/auth/me", headers={"Authorization": "Bearer token.jwt.abc"})

    assert respuesta.status_code == 200
    assert ruta.calls.last.request.headers["authorization"] == "Bearer token.jwt.abc"


def test_vehiculos_reenvia_a_ms2(gateway: TestClient, api_mock: respx.MockRouter) -> None:
    ruta = api_mock.get(f"{settings.MS2_URL}/vehiculos")

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 200
    assert str(ruta.calls.last.request.url) == f"{settings.MS2_URL}/vehiculos"


def test_query_string_se_mantiene(gateway: TestClient, api_mock: respx.MockRouter) -> None:
    ruta = api_mock.get(f"{settings.MS2_URL}/vehiculos", params={"patente": "AB1234"})

    respuesta = gateway.get("/api/vehiculos", params={"patente": "AB1234"})

    assert respuesta.status_code == 200
    assert ruta.calls.last.request.url.params["patente"] == "AB1234"


def test_patch_preserva_metodo_y_sub_path(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.patch(f"{settings.MS2_URL}/vehiculos/5")

    respuesta = gateway.patch("/api/vehiculos/5", json={"estado": "en_revision"})

    assert respuesta.status_code == 200
    assert ruta.calls.last.request.method == "PATCH"
    assert str(ruta.calls.last.request.url) == f"{settings.MS2_URL}/vehiculos/5"


@pytest.mark.parametrize("prefijo", ["ordenes", "orden", "clientes", "mecanicos"])
def test_rutas_de_ordenes_llegan_a_ms2(
    gateway: TestClient, api_mock: respx.MockRouter, prefijo: str
) -> None:
    ruta = api_mock.get(f"{settings.MS2_URL}/{prefijo}")

    respuesta = gateway.get(f"/api/{prefijo}")

    assert respuesta.status_code == 200
    assert ruta.called


def test_respuesta_del_microservicio_no_se_altera(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    cuerpo = {"detail": "Token inválido o expirado"}
    api_mock.get(f"{settings.MS1_URL}/auth/me").mock(
        return_value=httpx.Response(401, json=cuerpo)
    )

    respuesta = gateway.get("/api/auth/me")

    assert respuesta.status_code == 401
    assert respuesta.json() == cuerpo


def test_prefijo_desconocido_devuelve_404_sin_llamar_ms(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    respuesta = gateway.get("/api/desconocido")

    assert respuesta.status_code == 404
    assert api_mock.calls == []


def test_microservicio_caido_devuelve_502(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.post(f"{settings.MS1_URL}/auth/login").mock(
        side_effect=httpx.ConnectError("MS1 caído")
    )

    respuesta = gateway.post("/api/auth/login", json={"usuario": "admin"})

    assert respuesta.status_code == 502


@pytest.mark.parametrize(
    ("ruta", "esperado"),
    [
        ("auth/login", settings.MS1_URL),
        ("vehiculos", settings.MS2_URL),
        ("vehiculos/5", settings.MS2_URL),
        ("ordenes", settings.MS2_URL),
        ("clientes", settings.MS2_URL),
        ("MECANICOS", settings.MS2_URL),
        ("desconocido", None),
    ],
)
def test_resolver_microservicio(ruta: str, esperado: str | None) -> None:
    assert resolver_microservicio(ruta) == esperado