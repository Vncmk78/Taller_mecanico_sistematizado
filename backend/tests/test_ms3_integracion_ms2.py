"""Verificación de órdenes contra MS2 (sin levantar MS2: se simula httpx)."""
from __future__ import annotations

import httpx
import pytest

from services.ms3_presupuestos import integracion_ms2
from services.ms3_presupuestos.integracion_ms2 import (
    OrdenNoVisible,
    ServicioOrdenesNoDisponible,
    VerificadorOrdenesHttp,
    CoordinadorOrdenesHttp,
    DecisionAplicacionPendienteError,
)


def _simular(monkeypatch: pytest.MonkeyPatch, respuesta, headers_respuesta=None) -> list[dict]:
    llamadas: list[dict] = []

    def falso_get(url: str, *, headers: dict, timeout: float):
        llamadas.append({"url": url, "headers": headers, "timeout": timeout})
        if isinstance(respuesta, Exception):
            raise respuesta
        return httpx.Response(respuesta, headers=headers_respuesta, request=httpx.Request("GET", url))

    monkeypatch.setattr(integracion_ms2.httpx, "get", falso_get)
    return llamadas


def test_reenvia_el_mismo_jwt_a_ms2(monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas = _simular(monkeypatch, 200)
    VerificadorOrdenesHttp("http://ms2:8002/", 2.5).verificar_acceso(31, "token-del-cliente")
    assert llamadas == [{"url": "http://ms2:8002/ordenes/31",
                         "headers": {"Authorization": "Bearer token-del-cliente"},
                         "timeout": 2.5}]


def test_decidir_exige_propiedad_con_el_mismo_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas = _simular(monkeypatch, 200, headers_respuesta={"X-Orden-Propiedad-Verificada": "true"})
    VerificadorOrdenesHttp("http://ms2/", 2).verificar_propiedad(31, "jwt-original")
    assert llamadas == [{"url": "http://ms2/ordenes/31?solo_propietario=true",
                         "headers": {"Authorization": "Bearer jwt-original"}, "timeout": 2}]


def test_ms2_anterior_que_ignora_query_no_autoriza_decisiones(monkeypatch):
    _simular(monkeypatch, 200)
    with pytest.raises(ServicioOrdenesNoDisponible, match="no confirmó"):
        VerificadorOrdenesHttp("http://ms2", 2).verificar_propiedad(31, "jwt-original")


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


def test_coordinador_envia_solo_referencia_y_conserva_jwt(monkeypatch):
    llamadas = []
    def post(url, *, json, headers, timeout):
        llamadas.append((url, json, headers, timeout))
        return httpx.Response(200, json={"decision_id": 9, "orden_id": 31,
                                        "estado_aplicado": 8, "historial_id": 40})
    monkeypatch.setattr(integracion_ms2.httpx, "post", post)
    resultado = CoordinadorOrdenesHttp("http://ms2/", 2).aplicar(31, 9, "jwt-original")
    assert resultado.historial_id == 40
    assert llamadas == [("http://ms2/ordenes/31/decisiones-presupuesto", {"decision_id": 9},
                         {"Authorization": "Bearer jwt-original"}, 2)]


@pytest.mark.parametrize("respuesta", [
    httpx.Response(409, json={"detail": "Estado incompatible"}),
    httpx.Response(500), httpx.Response(200, text="no JSON"),
    httpx.Response(200, json={"decision_id": 10, "orden_id": 31,
                             "estado_aplicado": 8, "historial_id": 40}),
    httpx.ConnectError("caído"), httpx.ReadTimeout("timeout"),
])
def test_coordinacion_fallida_conserva_referencia_para_retry(monkeypatch, respuesta):
    def post(*args, **kwargs):
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta
    monkeypatch.setattr(integracion_ms2.httpx, "post", post)
    with pytest.raises(DecisionAplicacionPendienteError) as error:
        CoordinadorOrdenesHttp("http://ms2", 1).aplicar(31, 9, "t")
    assert error.value.decision_id == 9 and error.value.orden_id == 31
    if isinstance(respuesta, httpx.Response) and respuesta.status_code == 409:
        assert error.value.estado_ms2 == 409
        assert error.value.detalle_ms2 == "Estado incompatible"
