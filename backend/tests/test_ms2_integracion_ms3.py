"""MS2 obtiene hechos de MS3 autenticados; fallos y respuestas inválidas."""
import httpx
import pytest

from services.ms2_taller import integracion_ms3
from services.ms2_taller.integracion_ms3 import (
    DecisionNoAplicableError, DecisionNoVisibleError,
    ServicioPresupuestosNoDisponibleError, VerificadorDecisionesHttp,
)

HECHO = {"decision_id": 9, "orden_id": 31, "cliente_usuario_id": 42,
         "decision": "aprobado", "primera_decision": True,
         "repuestos_disponibles": True, "motivo": None}


def test_verifica_por_id_en_ms3_con_el_jwt_original(monkeypatch):
    llamadas = []
    def get(url, *, headers, timeout):
        llamadas.append((url, headers, timeout))
        return httpx.Response(200, json=HECHO)
    monkeypatch.setattr(integracion_ms3.httpx, "get", get)
    resultado = VerificadorDecisionesHttp("http://ms3/", 2).consultar(9, "jwt-original")
    assert resultado.repuestos_disponibles is True
    assert llamadas == [("http://ms3/presupuestos/decisiones/9",
                         {"Authorization": "Bearer jwt-original"}, 2)]


@pytest.mark.parametrize("estado,error", [
    (403, DecisionNoVisibleError), (404, DecisionNoVisibleError),
    (409, DecisionNoAplicableError), (401, ServicioPresupuestosNoDisponibleError),
    (500, ServicioPresupuestosNoDisponibleError),
])
def test_verificador_mapea_errores_http(monkeypatch, estado, error):
    monkeypatch.setattr(integracion_ms3.httpx, "get", lambda *a, **kw: httpx.Response(estado))
    with pytest.raises(error):
        VerificadorDecisionesHttp("http://ms3", 1).consultar(9, "t")


@pytest.mark.parametrize("respuesta", [
    httpx.Response(200, text="no JSON"),
    httpx.Response(200, json={**HECHO, "decision_id": 10}),
    httpx.Response(200, json={**HECHO, "estado_destino": 8}),
    httpx.Response(200, json={**HECHO, "repuestos_disponibles": "true"}),
    httpx.ConnectError("caído"), httpx.ReadTimeout("timeout"),
])
def test_hechos_invalidos_o_fallos_no_se_aceptan(monkeypatch, respuesta):
    def get(*args, **kwargs):
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta
    monkeypatch.setattr(integracion_ms3.httpx, "get", get)
    with pytest.raises(ServicioPresupuestosNoDisponibleError):
        VerificadorDecisionesHttp("http://ms3", 1).consultar(9, "t")
