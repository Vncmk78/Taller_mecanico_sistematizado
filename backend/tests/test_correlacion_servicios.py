"""Propagación del identificador de correlación en los microservicios (Semana 10).

SCRUM-582. Verifica `shared/correlacion.py` y su uso en MS1, MS2, MS3 y MS4:

- cada servicio devuelve `X-Request-ID` en toda respuesta, también en errores;
- respeta el ID recibido, reemplaza uno inválido y genera uno si falta;
- escribe una línea `evento=solicitud` con servicio, ID, método, ruta, estado y
  duración, sin el JWT ni la query string;
- reenvía a otros servicios **solo** el ID recibido (decisión C1 de
  `docs/estudio-correlacion-logs.md`).
"""
from __future__ import annotations

import logging
import re

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from shared.correlacion import (
    MiddlewareCorrelacion,
    cabeceras_correlacion,
    normalizar_request_id,
    request_id_actual,
)

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@pytest.fixture
def app_prueba() -> TestClient:
    """App mínima con el middleware: expone lo que ve el código de negocio."""
    app = FastAPI()
    app.add_middleware(MiddlewareCorrelacion, servicio="ms_prueba")

    @app.get("/eco")
    def eco() -> dict:
        return {"actual": request_id_actual(), "salientes": cabeceras_correlacion()}

    @app.get("/falla")
    def falla() -> None:
        raise HTTPException(status_code=503, detail="MS2 no disponible")

    return TestClient(app)


# --------------------------------------------------------------------------- #
# Middleware compartido                                                       #
# --------------------------------------------------------------------------- #

def test_respeta_el_id_recibido_y_lo_propaga(app_prueba: TestClient) -> None:
    r = app_prueba.get("/eco", headers={"X-Request-ID": "gw-abc-123"})
    assert r.headers["x-request-id"] == "gw-abc-123"
    assert r.json() == {
        "actual": "gw-abc-123",
        "salientes": {"X-Request-ID": "gw-abc-123"},
    }


def test_sin_cabecera_genera_uuid_pero_no_lo_propaga(app_prueba: TestClient) -> None:
    r = app_prueba.get("/eco")
    generado = r.headers["x-request-id"]
    assert _UUID.fullmatch(generado)
    assert r.json() == {"actual": generado, "salientes": {}}


@pytest.mark.parametrize("invalido", ["con espacio", "a" * 129, "x\ty", "a;b"])
def test_id_invalido_se_reemplaza(app_prueba: TestClient, invalido: str) -> None:
    r = app_prueba.get("/eco", headers={"X-Request-ID": invalido})
    assert _UUID.fullmatch(r.headers["x-request-id"])
    assert r.json()["salientes"] == {}


def test_las_respuestas_de_error_tambien_traen_el_id(app_prueba: TestClient) -> None:
    r = app_prueba.get("/falla", headers={"X-Request-ID": "err-1"})
    assert r.status_code == 503
    assert r.headers["x-request-id"] == "err-1"
    assert r.json() == {"detail": "MS2 no disponible"}  # body sin cambios


def test_fuera_de_una_peticion_no_hay_cabeceras() -> None:
    assert request_id_actual() is None
    assert cabeceras_correlacion() == {}


def test_normalizar_request_id() -> None:
    assert normalizar_request_id("abc-123") == "abc-123"
    assert normalizar_request_id(None) is None
    assert normalizar_request_id("") is None
    assert normalizar_request_id("abc\nevento=falso") is None


def test_log_por_peticion_sin_datos_sensibles(
    app_prueba: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="sgtm.correlacion"):
        app_prueba.get(
            "/falla?correo=cliente@ejemplo.cl",
            headers={"X-Request-ID": "log-9", "Authorization": "Bearer secreto.jwt.x"},
        )
    lineas = [r for r in caplog.records if r.name == "sgtm.correlacion"]
    assert len(lineas) == 1
    linea = lineas[0].getMessage()
    assert lineas[0].levelno == logging.ERROR  # 5xx
    for esperado in (
        "evento=solicitud",
        "servicio=ms_prueba",
        "request_id=log-9",
        "metodo=GET",
        "ruta=/falla",
        "estado_http=503",
        "duracion_ms=",
    ):
        assert esperado in linea
    assert "secreto" not in linea
    assert "cliente@ejemplo.cl" not in linea


# --------------------------------------------------------------------------- #
# Integrado en cada microservicio                                             #
# --------------------------------------------------------------------------- #

def _apps() -> list[tuple[str, FastAPI]]:
    from services.ms1_auth.main import app as ms1
    from services.ms2_taller.main import app as ms2
    from services.ms3_presupuestos.main import app as ms3

    return [("ms1_auth", ms1), ("ms2_taller", ms2), ("ms3_presupuestos", ms3)]


@pytest.mark.parametrize("indice", [0, 1, 2])
def test_cada_microservicio_devuelve_el_id_incluso_en_401(
    indice: int, caplog: pytest.LogCaptureFixture
) -> None:
    nombre, app = _apps()[indice]
    # Una ruta protegida sin token: error controlado del servicio, sin base.
    ruta = {
        "ms1_auth": "/auth/me",
        "ms2_taller": "/vehiculos",
        "ms3_presupuestos": "/repuestos",
    }[nombre]
    with caplog.at_level(logging.INFO, logger="sgtm.correlacion"):
        r = TestClient(app).get(ruta, headers={"X-Request-ID": f"{nombre}-1".replace("_", "-")})
    assert r.status_code in (401, 403)
    assert r.headers["x-request-id"] == f"{nombre}-1".replace("_", "-")
    mensajes = [x.getMessage() for x in caplog.records if x.name == "sgtm.correlacion"]
    assert any(f"servicio={nombre}" in m and "request_id=" in m for m in mensajes)


def test_ms3_reenvia_el_id_a_ms2(monkeypatch: pytest.MonkeyPatch) -> None:
    """La llamada saliente MS3 -> MS2 lleva el mismo X-Request-ID."""
    import httpx

    from services.ms3_presupuestos import integracion_ms2

    vistas: list[dict] = []

    def get_falso(url, *, headers, timeout, **_):
        vistas.append(dict(headers))
        raise httpx.ConnectError("MS2 apagado")

    monkeypatch.setattr(integracion_ms2.httpx, "get", get_falso)

    app = FastAPI()
    app.add_middleware(MiddlewareCorrelacion, servicio="ms3_presupuestos")

    @app.get("/probar")
    def probar() -> dict:
        verificador = integracion_ms2.obtener_verificador_ordenes()
        try:
            verificador.verificar_acceso(7, "jwt-prueba")
        except Exception as exc:  # noqa: BLE001
            return {"error": type(exc).__name__}
        return {"error": None}

    r = TestClient(app).get("/probar", headers={"X-Request-ID": "cadena-ms3-ms2"})
    assert r.json()["error"] == "ServicioOrdenesNoDisponible"
    assert vistas and vistas[0]["X-Request-ID"] == "cadena-ms3-ms2"
    assert vistas[0]["Authorization"] == "Bearer jwt-prueba"


def test_ms4_devuelve_el_id_y_lo_reenvia() -> None:
    from services.ms4_evidencias.main import app as ms4
    from services.ms4_evidencias.services.registro import cabeceras_request_id

    r = TestClient(ms4).get("/evidencias?orden_id=1", headers={"X-Request-ID": "ms4-77"})
    assert r.status_code == 401
    assert r.headers["x-request-id"] == "ms4-77"
    assert cabeceras_request_id() == {}  # fuera de una solicitud
