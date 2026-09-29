"""Pruebas de la estructura base de la API Gateway (Semana 1, tarea 1).

Verifican lo que la Gateway responde por sí misma, sin depender de que los
microservicios estén levantados: índice, healthcheck y CORS.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.config import GatewaySettings, settings
from gateway.main import app


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


def test_health_responde_ok(gateway: TestClient) -> None:
    respuesta = gateway.get("/api/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok", "servicio": settings.SERVICE_NAME}


def test_indice_lista_los_cuatro_microservicios(gateway: TestClient) -> None:
    respuesta = gateway.get("/")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "operativo"
    assert set(cuerpo["microservicios"]) == {
        "ms1_auth",
        "ms2_taller",
        "ms3_presupuestos",
        "ms4_evidencias",
    }


def test_cors_preflight_permite_origen_del_frontend(gateway: TestClient) -> None:
    origen = settings.CORS_ORIGINS[0]

    respuesta = gateway.options(
        "/api/health",
        headers={
            "Origin": origen,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == origen


def test_cors_rechaza_origen_no_permitido(gateway: TestClient) -> None:
    respuesta = gateway.get("/api/health", headers={"Origin": "http://sitio-ajeno.com"})

    assert "access-control-allow-origin" not in respuesta.headers


@pytest.mark.parametrize(
    "valor",
    ["http://a.cl,http://b.cl", '["http://a.cl", "http://b.cl"]'],
)
def test_cors_origins_acepta_comas_o_json(
    valor: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GATEWAY_CORS_ORIGINS", valor)

    assert GatewaySettings().CORS_ORIGINS == ["http://a.cl", "http://b.cl"]
