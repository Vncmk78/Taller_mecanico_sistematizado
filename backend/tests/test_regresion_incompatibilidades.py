"""Regresión de las incompatibilidades encontradas con los clientes (Semana 9).

Una prueba por incompatibilidad ya corregida, con su ID, para que no vuelva a
aparecer sin que falle algo con nombre propio. Se prueban contra el
`/openapi.json` que descargan los clientes (web y app de Integra IV) y contra la
documentación que el equipo móvil usa para integrarse.

| ID | Origen | Qué se corrigió |
|---|---|---|
| B-01 … B-04 | `docs/contratos-integracion-iv.md` §4 | Estados y ejemplos que faltaban en el contrato de la app móvil |
| D-01, D-02 | `docs/diferencias-contrato-consumo-real.md` §3 | Respuesta de cancelación y campos que siempre vienen |
| H-01 | `docs/estudio-consumo-api-movil-redes-externas.md` §3 | `Retry-After` expuesto por CORS (`test_cabeceras_cliente_movil.py`) |
| O-01 | `docs/contratos-integracion-iv.md` §5 | La matriz de roles negaba rutas publicadas |

D-03 (roles múltiples en el frontend) está cubierta en
`frontend/src/infrastructure/api/AuthService.test.ts` y
`ProtectedRoute.test.tsx`. Las incompatibilidades nuevas se registran en su
documento con un ID nuevo y se agregan aquí al corregirse.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gateway.main import app

DOCS = Path(__file__).resolve().parents[1] / "docs"
_METODOS = ("get", "post", "put", "patch", "delete")
_REF_RUTA = re.compile(r"`(GET|POST|PUT|PATCH|DELETE) (/api/[^`?\s]*)")


@pytest.fixture(scope="module")
def contrato() -> dict:
    respuesta = TestClient(app).get("/openapi.json")
    assert respuesta.status_code == 200
    return respuesta.json()


def _operacion(contrato: dict, metodo: str, ruta: str) -> dict:
    return contrato["paths"][ruta][metodo]


def _json(operacion: dict, estado: str) -> dict:
    return operacion["responses"][estado]["content"]["application/json"]


def _tiene_ejemplo(contenido: dict) -> bool:
    return bool(contenido.get("examples")) or "example" in contenido


def _esquema(contrato: dict, nombre: str) -> dict:
    return contrato["components"]["schemas"][nombre]


def _normalizar(ruta: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", ruta.rstrip("/"))


def _rutas_publicadas(contrato: dict) -> set[tuple[str, str]]:
    return {
        (metodo.upper(), _normalizar(ruta))
        for ruta, operaciones in contrato["paths"].items()
        for metodo in operaciones
        if metodo in _METODOS
    }


# ── B-01: estados del login que la app debe manejar ─────────────────────────


def test_b01_login_publica_403_422_y_429(contrato: dict) -> None:
    respuestas = _operacion(contrato, "post", "/api/auth/login")["responses"]

    assert {"401", "403", "422", "429"} <= set(respuestas)


def test_b01_429_del_login_declara_retry_after(contrato: dict) -> None:
    bloqueo = _operacion(contrato, "post", "/api/auth/login")["responses"]["429"]

    assert "Retry-After" in bloqueo.get("headers", {})


# ── B-02: id de vehículo inválido vs. vehículo inexistente ──────────────────


def test_b02_detalle_de_vehiculo_publica_422_y_no_403(contrato: dict) -> None:
    respuestas = _operacion(contrato, "get", "/api/vehiculos/{vehiculo_id}")[
        "responses"
    ]

    assert "422" in respuestas
    assert "404" in respuestas
    # El Mecánico no recibe 403 aquí: fuera de sus órdenes responde 404.
    assert "403" not in respuestas


# ── B-03 y B-04: ejemplos de éxito que la app usa como mock ─────────────────


@pytest.mark.parametrize(
    ("metodo", "estado"), [("get", "200"), ("post", "201")]
)
def test_b03_bitacora_trae_ejemplo_de_exito(
    contrato: dict, metodo: str, estado: str
) -> None:
    operacion = _operacion(contrato, metodo, "/api/ordenes/{orden_id}/bitacora")

    assert _tiene_ejemplo(_json(operacion, estado))


@pytest.mark.parametrize("estado", ["201", "200"])
def test_b04_cancelacion_trae_ejemplo_creada_y_repetida(
    contrato: dict, estado: str
) -> None:
    operacion = _operacion(contrato, "post", "/api/ordenes/{orden_id}/cancelacion")

    assert _tiene_ejemplo(_json(operacion, estado))


# ── D-01: la cancelación responde una solicitud, no una orden ───────────────


@pytest.mark.parametrize("estado", ["201", "200"])
def test_d01_cancelacion_publica_solicitud_y_no_orden(
    contrato: dict, estado: str
) -> None:
    operacion = _operacion(contrato, "post", "/api/ordenes/{orden_id}/cancelacion")

    referencia = _json(operacion, estado)["schema"]["$ref"]
    assert referencia.endswith("/SolicitudCancelacionRespuesta")
    propiedades = _esquema(contrato, "SolicitudCancelacionRespuesta")["properties"]
    assert "estado_codigo" not in propiedades


# ── D-02: campos que siempre vienen deben publicarse como obligatorios ──────


@pytest.mark.parametrize(
    ("esquema", "campo"),
    [
        ("TokenRespuesta", "token_type"),
        ("BitacoraRespuesta", "repuestos"),
        ("ResultadoOperacion", "decision_id"),
        ("ResultadoOperacion", "aplicacion_en_orden"),
    ],
)
def test_d02_campo_siempre_presente_es_obligatorio(
    contrato: dict, esquema: str, campo: str
) -> None:
    definicion = _esquema(contrato, esquema)

    assert campo in definicion["properties"]
    assert campo in definicion.get("required", [])


# ── O-01: la documentación de integración no puede negar ni inventar rutas ──


@pytest.mark.parametrize(
    "documento",
    [
        "matriz-autorizacion-roles.md",
        "contratos-integracion-iv.md",
        "estudio-consumo-api-movil-redes-externas.md",
    ],
)
def test_o01_rutas_citadas_en_la_documentacion_estan_publicadas(
    contrato: dict, documento: str
) -> None:
    texto = (DOCS / documento).read_text(encoding="utf-8")
    citadas = set(_REF_RUTA.findall(texto))
    publicadas = _rutas_publicadas(contrato)

    faltantes = sorted(
        f"{metodo} {ruta}"
        for metodo, ruta in citadas
        if (metodo, _normalizar(ruta)) not in publicadas
    )
    assert citadas
    assert faltantes == []


def test_o01_matriz_no_dice_que_una_ruta_publicada_no_existe(contrato: dict) -> None:
    texto = (DOCS / "matriz-autorizacion-roles.md").read_text(encoding="utf-8")
    publicadas = _rutas_publicadas(contrato)
    niega = re.compile(
        r"`(GET|POST|PUT|PATCH|DELETE) (/api/[^`?\s]*)`[^.|]{0,40}?\*{0,2}no\s+existe",
        re.IGNORECASE,
    )

    negadas = [
        f"{metodo} {ruta}"
        for metodo, ruta in niega.findall(texto)
        if (metodo, _normalizar(ruta)) in publicadas
    ]
    assert negadas == []


def test_o01_vehiculos_asignados_publicada_para_el_mecanico(contrato: dict) -> None:
    respuestas = _operacion(contrato, "get", "/api/vehiculos/asignados")["responses"]

    assert {"200", "401", "403"} <= set(respuestas)
