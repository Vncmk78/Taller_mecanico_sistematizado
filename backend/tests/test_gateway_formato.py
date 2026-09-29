"""Pruebas del formato común de solicitudes, respuestas y errores (Semana 2).

Verifican el contrato definido en `gateway/README.md` (sección "Formato
común"): las respuestas exitosas y los errores generados por los
microservicios pasan sin modificarse, mientras que los errores propios de la
Gateway (404, 405, 502 y 500) usan el cuerpo `{"detail": str, "error": {...}}`
y siempre viajan con la cabecera `X-Request-ID`.
"""
from __future__ import annotations

import logging
import re

import httpx
import pytest
import respx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from gateway.config import settings
from gateway.errores import (
    ERROR_HTTP,
    ERROR_INTERNO,
    METODO_NO_PERMITIDO,
    MICROSERVICIO_INALCANZABLE,
    RUTA_NO_ENCONTRADA,
)
from gateway.main import app

_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


@pytest.fixture
def api_mock() -> respx.MockRouter:
    with respx.mock(assert_all_mocked=True) as mock:
        yield mock


def _cuerpo_de_error(respuesta) -> dict:
    """Valida la forma mínima del formato común y devuelve el cuerpo."""
    cuerpo = respuesta.json()
    assert isinstance(cuerpo["detail"], str)
    assert isinstance(cuerpo["error"], dict)
    for clave in ("codigo", "ruta", "request_id"):
        assert isinstance(cuerpo["error"][clave], str)
    assert isinstance(cuerpo["error"]["estado"], int)
    return cuerpo


def test_404_de_ruta_desconocida_usa_formato_comun(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    respuesta = gateway.get("/api/desconocido")

    assert respuesta.status_code == 404
    cuerpo = _cuerpo_de_error(respuesta)
    assert cuerpo["detail"] == "No hay microservicio para '/desconocido'"
    assert cuerpo["error"]["codigo"] == RUTA_NO_ENCONTRADA
    assert cuerpo["error"]["estado"] == 404
    assert cuerpo["error"]["ruta"] == "/api/desconocido"
    assert api_mock.calls == []


def test_404_fuera_de_api_tambien_usa_formato_comun(gateway: TestClient) -> None:
    respuesta = gateway.get("/no-existe")

    assert respuesta.status_code == 404
    cuerpo = _cuerpo_de_error(respuesta)
    assert cuerpo["error"]["codigo"] == RUTA_NO_ENCONTRADA
    assert cuerpo["detail"] == "Ruta no encontrada"


def test_405_usa_formato_comun(gateway: TestClient) -> None:
    # POST "/" matchea el GET del índice; la ruta no acepta otros métodos.
    respuesta = gateway.post("/")

    assert respuesta.status_code == 405
    cuerpo = _cuerpo_de_error(respuesta)
    assert cuerpo["error"]["codigo"] == METODO_NO_PERMITIDO
    assert cuerpo["error"]["estado"] == 405
    assert cuerpo["error"]["ruta"] == "/"
    assert cuerpo["detail"] == "Método no permitido"


def test_502_microservicio_caido_usa_formato_comun(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.post(f"{settings.MS2_URL}/ordenes").mock(
        side_effect=httpx.ConnectError("MS2 caído")
    )

    respuesta = gateway.post("/api/ordenes", json={"descripcion": "cambio de aceite"})

    assert respuesta.status_code == 502
    cuerpo = _cuerpo_de_error(respuesta)
    assert cuerpo["error"]["codigo"] == MICROSERVICIO_INALCANZABLE
    assert cuerpo["error"]["estado"] == 502
    assert cuerpo["detail"] == "El servicio no está disponible. Intente más tarde."
    assert settings.MS2_URL not in respuesta.text
    assert "MS2 caído" not in respuesta.text


def test_error_interno_usa_app_real_con_cors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reventar(ruta: str) -> None:
        raise ValueError("secreto interno: la contraseña de la base de datos")

    monkeypatch.setattr("gateway.routers.proxy.resolver_microservicio", reventar)

    cliente = TestClient(app, raise_server_exceptions=False)
    respuesta = cliente.get(
        "/api/vehiculos", headers={"Origin": "http://localhost:5173"}
    )

    assert respuesta.status_code == 500
    cuerpo = _cuerpo_de_error(respuesta)
    assert cuerpo["detail"] == "Ocurrió un error inesperado en la Gateway."
    assert cuerpo["error"]["codigo"] == ERROR_INTERNO
    assert cuerpo["error"]["estado"] == 500
    assert cuerpo["error"]["ruta"] == "/api/vehiculos"
    assert "secreto" not in respuesta.text
    # El 500 sale por el middleware interno, dentro de CORS: debe incluir la
    # cabecera y el X-Request-ID, igual que cualquier otra respuesta.
    assert (
        respuesta.headers["access-control-allow-origin"] == "http://localhost:5173"
    )
    request_id = respuesta.headers["x-request-id"]
    assert _UUID.fullmatch(request_id)
    assert cuerpo["error"]["request_id"] == request_id


def test_error_interno_se_registra_en_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def reventar(ruta: str) -> None:
        raise ValueError("secreto interno")

    monkeypatch.setattr("gateway.routers.proxy.resolver_microservicio", reventar)

    cliente = TestClient(app, raise_server_exceptions=False)
    caplog.set_level(logging.ERROR, logger="gateway")
    respuesta = cliente.get("/api/vehiculos")

    assert respuesta.status_code == 500
    request_id = respuesta.headers["x-request-id"]
    mensajes = [r.getMessage() for r in caplog.records]
    assert any(
        "Error no controlado en /api/vehiculos" in mensaje and request_id in mensaje
        for mensaje in mensajes
    )


def test_http_exception_fuera_de_catalogo_usa_error_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def rechazar(ruta: str) -> None:
        raise HTTPException(status_code=400, detail="Algo raro")

    monkeypatch.setattr("gateway.routers.proxy.resolver_microservicio", rechazar)

    respuesta = TestClient(app).get("/api/vehiculos")

    assert respuesta.status_code == 400
    cuerpo = _cuerpo_de_error(respuesta)
    assert cuerpo["error"]["codigo"] == ERROR_HTTP
    assert cuerpo["error"]["estado"] == 400
    assert cuerpo["detail"] == "Algo raro"


def test_request_id_generado_y_sincronizado_con_la_cabecera(
    gateway: TestClient,
) -> None:
    respuesta = gateway.get("/api/desconocido")

    assert respuesta.status_code == 404
    request_id = respuesta.headers["x-request-id"]
    assert _UUID.fullmatch(request_id)
    assert respuesta.json()["error"]["request_id"] == request_id


def test_request_id_valido_se_respeta_y_se_propaga_al_ms(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(200, json=[])
    )

    respuesta = gateway.get("/api/vehiculos", headers={"X-Request-ID": "abc-123"})

    assert respuesta.status_code == 200
    assert respuesta.headers["x-request-id"] == "abc-123"
    assert ruta.calls.last.request.headers["x-request-id"] == "abc-123"


def test_request_id_invalido_se_reemplaza_por_uuid(gateway: TestClient) -> None:
    respuesta = gateway.get(
        "/api/desconocido", headers={"X-Request-ID": "x" * 200}
    )

    assert respuesta.status_code == 404
    assert _UUID.fullmatch(respuesta.headers["x-request-id"])


def test_request_id_con_caracteres_invalidos_se_reemplaza(
    gateway: TestClient,
) -> None:
    respuesta = gateway.get(
        "/api/desconocido", headers={"X-Request-ID": "id con_!_espacios"}
    )

    assert respuesta.status_code == 404
    assert _UUID.fullmatch(respuesta.headers["x-request-id"])


def test_request_id_generado_se_propaga_al_ms(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(200, json=[])
    )

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 200
    request_id = respuesta.headers["x-request-id"]
    assert _UUID.fullmatch(request_id)
    assert ruta.calls.last.request.headers["x-request-id"] == request_id


def test_error_del_microservicio_pasa_tal_cual(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    cuerpo = {"detail": "Ya existe un vehículo con esa patente"}
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(409, json=cuerpo)
    )

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 409
    assert respuesta.json() == cuerpo
    assert _UUID.fullmatch(respuesta.headers["x-request-id"])


@pytest.mark.parametrize(
    ("verificacion", "esperado"),
    [
        (lambda g: g.get("/api/desconocido"), RUTA_NO_ENCONTRADA),
        (lambda g: g.post("/"), METODO_NO_PERMITIDO),
    ],
)
def test_detail_siempre_string(
    gateway: TestClient, verificacion, esperado: str
) -> None:
    respuesta = verificacion(gateway)

    assert isinstance(respuesta.json()["detail"], str)
    assert respuesta.json()["error"]["codigo"] == esperado