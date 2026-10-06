"""Verificación de órdenes contra MS2 (sin levantar MS2: se simula httpx)."""
from __future__ import annotations

import httpx
import pytest

from services.ms3_presupuestos import integracion_ms2
from services.ms3_presupuestos.integracion_ms2 import (
    OrdenNoVisible,
    ServicioOrdenesNoDisponible,
    VerificadorOrdenesHttp,
)


def _simular(monkeypatch: pytest.MonkeyPatch, respuesta) -> list[dict]:
    llamadas: list[dict] = []

    def falso_get(url: str, *, headers: dict, timeout: float):
        llamadas.append({"url": url, "headers": headers, "timeout": timeout})
        if isinstance(respuesta, Exception):
            raise respuesta
        return httpx.Response(respuesta, request=httpx.Request("GET", url))

    monkeypatch.setattr(integracion_ms2.httpx, "get", falso_get)
    return llamadas


def test_reenvia_el_mismo_jwt_a_ms2(monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas = _simular(monkeypatch, 200)
    VerificadorOrdenesHttp("http://ms2:8002/", 2.5).verificar_acceso(31, "token-del-cliente")
    assert llamadas == [{"url": "http://ms2:8002/ordenes/31",
                         "headers": {"Authorization": "Bearer token-del-cliente"},
                         "timeout": 2.5}]


@pytest.mark.parametrize("codigo", [403, 404])
def test_orden_ajena_o_inexistente(monkeypatch: pytest.MonkeyPatch, codigo: int) -> None:
    _simular(monkeypatch, codigo)
    with pytest.raises(OrdenNoVisible):
        VerificadorOrdenesHttp("http://ms2", 1).verificar_acceso(31, "t")


@pytest.mark.parametrize("respuesta", [500, 401, httpx.ConnectError("caído"),
                                       httpx.ReadTimeout("lento")])
def test_ms2_no_disponible(monkeypatch: pytest.MonkeyPatch, respuesta) -> None:
    _simular(monkeypatch, respuesta)
    with pytest.raises(ServicioOrdenesNoDisponible):
        VerificadorOrdenesHttp("http://ms2", 1).verificar_acceso(31, "t")


def test_dependencia_usa_la_configuracion() -> None:
    verificador = integracion_ms2.obtener_verificador_ordenes()
    assert verificador.url_base == integracion_ms2.settings.MS2_URL.rstrip("/")
    assert verificador.timeout == integracion_ms2.settings.MS2_TIMEOUT_SEGUNDOS
