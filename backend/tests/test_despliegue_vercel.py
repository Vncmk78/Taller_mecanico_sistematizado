"""Regresión del ciclo rechazado por Vercel y del transporte MS2 → MS3."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import httpx
import pytest

from services.ms2_taller.config import Settings
from services.ms2_taller.direccion_ms3 import cabeceras_para_ms3, url_ms3_por_defecto
from services.ms2_taller.integracion_ms3 import (
    VerificadorAprobacionInicialHttp, VerificadorDecisionesHttp,
    VerificadorDisponibilidadRepuestosHttp, VerificadorEnviosPresupuestoHttp,
)


@pytest.fixture(autouse=True)
def entorno_controlado(monkeypatch):
    for nombre in ["VERCEL", "VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL",
                   "VERCEL_AUTOMATION_BYPASS_SECRET", "MS2_MS3_URL"]:
        monkeypatch.delenv(nombre, raising=False)


def _sin_ciclos(servicios):
    visitados, camino = set(), []

    def visitar(nombre):
        assert nombre in servicios, f"Servicio no declarado: {nombre}"
        if nombre in camino:
            raise AssertionError(" -> ".join(camino + [nombre]))
        if nombre in visitados:
            return
        camino.append(nombre)
        for enlace in servicios[nombre].get("bindings", []):
            visitar(enlace["service"])
        camino.pop()
        visitados.add(nombre)

    for nombre in servicios:
        visitar(nombre)


def _servicios():
    return json.loads((Path(__file__).resolve().parents[2] / "vercel.json").read_text())["services"]


def test_bindings_publicados_no_contienen_ciclos():
    _sin_ciclos(_servicios())


def test_el_guard_detecta_el_ciclo_del_despliegue_fallido():
    servicios = copy.deepcopy(_servicios())
    servicios["ms-taller"]["bindings"].append(
        {"type": "service", "service": "ms-presupuestos", "format": "url", "env": "MS2_MS3_URL"}
    )
    with pytest.raises(AssertionError, match="ms-taller -> ms-presupuestos -> ms-taller"):
        _sin_ciclos(servicios)


def _settings(**campos):
    return Settings(_env_file=None, JWT_SECRET_KEY="clave-exclusiva-de-prueba-vercel-123456", **campos)


def test_local_y_kubero_conservan_la_url_configurable(monkeypatch):
    assert _settings().MS3_URL == "http://localhost:8003"
    monkeypatch.setenv("MS2_MS3_URL", "http://ms3-interno:8000")
    assert _settings().MS3_URL == "http://ms3-interno:8000"


def test_vercel_usa_el_mismo_despliegue_y_no_el_alias_de_produccion(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_URL", "taller-preview-abc.vercel.app")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "tallerconect.vercel.app")
    assert _settings().MS3_URL == "https://taller-preview-abc.vercel.app/ms3"
    monkeypatch.setenv("MS2_MS3_URL", "https://ms3-explicito.example.test")
    assert _settings().MS3_URL == "https://ms3-explicito.example.test"


@pytest.mark.parametrize("host", ["", "https://taller.vercel.app", "otro@taller.vercel.app",
                                  "taller.vercel.app/ruta", "taller.vercel.app?clave=valor",
                                  "taller.vercel.app:443", "taller..vercel.app"])
def test_host_de_sistema_invalido_no_cae_a_localhost(monkeypatch, host):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_URL", host)
    with pytest.raises(ValueError, match="VERCEL_URL"):
        url_ms3_por_defecto()
    # Una configuración explícita sigue siendo válida aunque no haya URL automática.
    assert _settings(MS3_URL="http://ms3:8000").MS3_URL == "http://ms3:8000"


@pytest.mark.parametrize("destino", ["http://localhost:8003", "https://ajeno.vercel.app/ms3",
                                     "https://taller.vercel.app/ms3.evil", "https://taller.vercel.app/ms1",
                                     "http://taller.vercel.app/ms3", "https://taller.vercel.app.evil/ms3"])
def test_secreto_de_plataforma_no_sale_a_otro_destino(monkeypatch, destino):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_URL", "taller.vercel.app")
    monkeypatch.setenv("VERCEL_AUTOMATION_BYPASS_SECRET", "secreto-de-plataforma-de-prueba")
    assert cabeceras_para_ms3(destino, "jwt-usuario") == {"Authorization": "Bearer jwt-usuario"}


@pytest.mark.parametrize("secreto", [None, "secreto-de-plataforma-de-prueba"])
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
def test_todas_las_consultas_conservan_jwt_y_ruta_al_usar_url_publica(
    monkeypatch, secreto, verificador, argumentos, ruta, respuesta,
):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_URL", "taller.vercel.app")
    if secreto is not None:
        monkeypatch.setenv("VERCEL_AUTOMATION_BYPASS_SECRET", secreto)
    llamadas = []

    def get(url, *, headers, timeout):
        llamadas.append(url)
        assert url == "https://taller.vercel.app/ms3" + ruta
        esperadas = {"Authorization": "Bearer jwt-usuario"}
        if secreto is not None:
            esperadas["x-vercel-protection-bypass"] = secreto
        assert headers == esperadas
        assert timeout == 3
        return httpx.Response(200, json=respuesta)

    monkeypatch.setattr(httpx, "get", get)
    verificador(url_ms3_por_defecto(), 3).consultar(*argumentos, "jwt-usuario")
    assert len(llamadas) == 1
