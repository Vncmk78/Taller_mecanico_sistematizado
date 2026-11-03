"""Contratos HTTP externos: respuesta incompleta o incompatible falla cerrada."""
from __future__ import annotations

import httpx
import pytest

from services.ms2_taller.integracion_ms1 import (
    MecanicoNoValidoError, ServicioUsuariosNoDisponibleError, VerificadorMecanicosHttp,
)
from services.ms3_presupuestos.integracion_ms2 import (
    OrdenNoVisible, ServicioOrdenesNoDisponible, VerificadorOrdenesHttp,
)
from shared.auth import NombreRol, PrincipalAutenticado


def _respuesta(monkeypatch, respuesta):
    def get(url, *, headers, timeout):
        assert headers == {"Authorization": "Bearer jwt-prueba"}
        assert timeout == 2.5
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta
    monkeypatch.setattr(httpx, "get", get)


@pytest.mark.parametrize("respuesta", [
    httpx.Response(401), httpx.Response(403), httpx.Response(500),
    httpx.Response(200, text="no es JSON"), httpx.Response(200, json=None),
    httpx.Response(200, json={"id": 77}),
    httpx.Response(200, json={"id": 88, "is_active": True, "roles": ["mecanico"]}),
    httpx.Response(200, json={"id": 77, "is_active": "true", "roles": ["mecanico"]}),
    httpx.Response(200, json={"id": 77, "is_active": True, "roles": "mecanico"}),
    httpx.ConnectError("error con detalles privados"), httpx.ReadTimeout("timeout"),
])
def test_ms1_no_utilizable_no_se_acepta_como_mecanico(monkeypatch, respuesta):
    _respuesta(monkeypatch, respuesta)
    with pytest.raises(ServicioUsuariosNoDisponibleError):
        VerificadorMecanicosHttp("http://ms1/", 2.5).verificar(77, "jwt-prueba")


@pytest.mark.parametrize("respuesta", [
    httpx.Response(404),
    httpx.Response(200, json={"id": 77, "is_active": False, "roles": ["mecanico"]}),
    httpx.Response(200, json={"id": 77, "is_active": True, "roles": ["cliente"]}),
])
def test_ms1_destino_invalido_se_rechaza(monkeypatch, respuesta):
    _respuesta(monkeypatch, respuesta)
    with pytest.raises(MecanicoNoValidoError):
        VerificadorMecanicosHttp("http://ms1", 2.5).verificar(77, "jwt-prueba")


def test_ms1_multirrol_activo_y_destino_correcto(monkeypatch):
    def get(url, *, headers, timeout):
        assert url == "http://ms1/auth/usuarios/77"
        assert headers == {"Authorization": "Bearer jwt-prueba"}
        assert timeout == 2.5
        return httpx.Response(200, json={"id": 77, "is_active": True,
                                        "roles": ["cliente", "mecanico"]})
    monkeypatch.setattr(httpx, "get", get)
    VerificadorMecanicosHttp("http://ms1/", 2.5).verificar(77, "jwt-prueba")


@pytest.mark.parametrize("respuesta", [
    httpx.Response(401), httpx.Response(500),
    httpx.Response(200, text="no JSON"), httpx.Response(200, json=[]),
    httpx.Response(200, json={"orden_id": 31}),
    httpx.Response(200, json={"orden_id": 32, "mecanico_actual_id": 77}),
    httpx.Response(200, json={"orden_id": 31, "mecanico_actual_id": "77"}),
    httpx.ConnectError("caído"), httpx.ReadTimeout("timeout"),
])
def test_ms2_no_utilizable_no_autoriza_creacion(monkeypatch, respuesta):
    _respuesta(monkeypatch, respuesta)
    principal = PrincipalAutenticado(usuario_id=77, roles=frozenset({NombreRol.MECANICO}))
    with pytest.raises(ServicioOrdenesNoDisponible):
        VerificadorOrdenesHttp("http://ms2", 2.5).verificar_creacion_presupuesto(
            31, "jwt-prueba", principal,
        )


@pytest.mark.parametrize("respuesta", [
    httpx.Response(403), httpx.Response(404),
    httpx.Response(200, json={"orden_id": 31, "mecanico_actual_id": None}),
    httpx.Response(200, json={"orden_id": 31, "mecanico_actual_id": 88}),
])
def test_ms2_orden_no_asignada_o_inexistente_rechaza(monkeypatch, respuesta):
    _respuesta(monkeypatch, respuesta)
    principal = PrincipalAutenticado(usuario_id=77, roles=frozenset({NombreRol.MECANICO}))
    with pytest.raises(OrdenNoVisible):
        VerificadorOrdenesHttp("http://ms2", 2.5).verificar_creacion_presupuesto(
            31, "jwt-prueba", principal,
        )


def test_dependencia_ms1_usa_url_y_timeout_configurados(monkeypatch):
    from services.ms2_taller import integracion_ms1
    monkeypatch.setattr(integracion_ms1.settings, "MS1_URL", "http://ms1-interno/")
    monkeypatch.setattr(integracion_ms1.settings, "MS1_TIMEOUT_SEGUNDOS", 2.5)
    verificador = integracion_ms1.obtener_verificador_mecanicos()
    assert verificador.url_base == "http://ms1-interno"
    assert verificador.timeout == 2.5


def test_contrato_publica_rechazos_por_validacion_externa():
    from gateway.main import app as gateway
    from services.ms2_taller.main import app as ms2
    from services.ms3_presupuestos.main import app as ms3

    publicadas = gateway.openapi()["paths"]
    asignacion = publicadas["/api/ordenes/{orden_id}/mecanico"]["put"]
    creacion = publicadas["/api/presupuestos"]["post"]
    assert {"422", "503"} <= asignacion["responses"].keys()
    assert {"404", "503"} <= creacion["responses"].keys()
    for operacion in [asignacion, creacion]:
        esquema = operacion["responses"]["503"]["content"]["application/json"]["schema"]
        assert {"$ref": "#/components/schemas/ErrorDetalle"} in esquema["oneOf"]
    assert "503" in ms2.openapi()["paths"]["/ordenes/{orden_id}/mecanico"]["put"]["responses"]
    assert {"404", "503"} <= ms3.openapi()["paths"]["/presupuestos"]["post"]["responses"].keys()
