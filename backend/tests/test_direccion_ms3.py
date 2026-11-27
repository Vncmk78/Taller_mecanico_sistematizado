"""Regresión de la URL interna MS2 → MS3 y de sus cabeceras."""
from __future__ import annotations

import httpx
import pytest

from services.ms2_taller.config import Settings
from services.ms2_taller.direccion_ms3 import cabeceras_para_ms3, url_ms3_por_defecto
from services.ms2_taller.integracion_ms3 import (
    VerificadorAprobacionInicialHttp,
    VerificadorDecisionesHttp,
    VerificadorDisponibilidadRepuestosHttp,
    VerificadorEnviosPresupuestoHttp,
)


@pytest.fixture(autouse=True)
def sin_url_configurada(monkeypatch):
    monkeypatch.delenv("MS2_MS3_URL", raising=False)


def _settings(**campos):
    return Settings(
        _env_file=None,
        JWT_SECRET_KEY="clave-exclusiva-de-prueba-ms2-ms3-123456",
        **campos,
    )


def test_local_usa_el_puerto_por_defecto_y_acepta_url_interna():
    assert url_ms3_por_defecto() == "http://localhost:8003"
    assert _settings().MS3_URL == "http://localhost:8003"
    assert _settings(MS3_URL="http://ms3-interno:8000").MS3_URL == "http://ms3-interno:8000"


def test_cabeceras_solo_llevan_el_jwt_del_usuario():
    assert cabeceras_para_ms3("http://ms3-interno:8000", "jwt-usuario") == {
        "Authorization": "Bearer jwt-usuario"
    }


@pytest.mark.parametrize(("verificador", "argumentos", "ruta", "respuesta"), [
    (VerificadorAprobacionInicialHttp, (31,), "/presupuestos/ordenes/31/primera-aprobacion",
     {"orden_id": 31, "aprobacion_registrada": False}),
    (VerificadorDecisionesHttp, (9,), "/presupuestos/decisiones/9",
     {"decision_id": 9, "orden_id": 31, "cliente_usuario_id": 42, "decision": "aprobado",
      "primera_decision": True, "repuestos_disponibles": True, "motivo": None}),
    (VerificadorEnviosPresupuestoHttp, (7,), "/presupuestos/7/envio-inicial",
     {"presupuesto_id": 7, "orden_id": 31, "envio_inicial_confirmado": True}),
    (VerificadorDisponibilidadRepuestosHttp, (31, "reserva-1"),
     "/inventario/ordenes/31/disponibilidad/reserva-1",
     {"orden_id": 31, "clave_operacion": "reserva-1", "reserva_confirmada": True}),
])
def test_todas_las_consultas_conservan_url_y_jwt(
    monkeypatch, verificador, argumentos, ruta, respuesta
):
    monkeypatch.setenv("MS2_MS3_URL", "http://ms3-interno:8000")
    llamadas = []

    def get(url, *, headers, timeout):
        llamadas.append(url)
        assert url == "http://ms3-interno:8000" + ruta
        assert headers == {"Authorization": "Bearer jwt-usuario"}
        assert timeout == 3
        return httpx.Response(200, json=respuesta)

    monkeypatch.setattr(httpx, "get", get)
    verificador("http://ms3-interno:8000", 3).consultar(*argumentos, "jwt-usuario")
    assert len(llamadas) == 1
