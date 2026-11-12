"""Validación de los contratos que necesita la app móvil (Taller de Integración IV).

Toma el catálogo cerrado `gateway/contratos/integracion_iv.py` y, para cada
operación, comprueba en el OpenAPI que publica la Gateway que la app móvil
pueda consumirla sin adivinar nada:

* `publicada`: la ruta y el método existen en `/openapi.json`.
* `seguridad`: las protegidas exigen `bearer`; las públicas no.
* `respuesta_exito`: hay una respuesta 2xx `application/json` con esquema.
* `ejemplo_exito`: esa respuesta trae un ejemplo (la app lo usa como mock).
* `estados`: se publican los estados que la app debe manejar (401 en las
  protegidas, 403 si algún rol móvil es rechazado, 404 con parámetros de ruta,
  422 con parámetros o body, 502 y 504 siempre, más los requeridos del catálogo).
* `estados_microservicio`: todo estado que declara el microservicio dueño
  también lo publica la Gateway.
* `campos_microservicio`: parámetros, campos y obligatoriedad del body y de la
  respuesta 2xx coinciden con el OpenAPI real del microservicio.

Las brechas detectadas en la validación de Semana 8 (B-01 a B-04) se
corrigieron en la versión estable 1.0.0. Una brecha nueva se registra en
`_BRECHAS` como `xfail` estricto con su ID de `docs/contratos-integracion-iv.md`.
"""
from __future__ import annotations

from typing import Any

import pytest

from gateway.contratos.integracion_iv import (
    CLIENTE,
    MECANICO,
    OPERACIONES_INTEGRACION_IV,
    OperacionMovil,
)
from gateway.main import app as gateway_app
from services.ms1_auth.main import app as app_ms1
from services.ms2_taller.main import app as app_ms2
from services.ms3_presupuestos.main import app as app_ms3
from services.ms4_evidencias.main import app as app_ms4

_JSON = "application/json"
_CABECERAS_GATEWAY = {"X-Request-ID"}
_APP_POR_PREFIJO = {
    "auth": app_ms1,
    "notificaciones": app_ms1,
    "vehiculos": app_ms2,
    "clientes": app_ms2,
    "ordenes": app_ms2,
    "presupuestos": app_ms3,
    "evidencias": app_ms4,
}

_COMPROBACIONES = (
    "publicada",
    "seguridad",
    "respuesta_exito",
    "ejemplo_exito",
    "estados",
    "estados_microservicio",
    "campos_microservicio",
)

# Brechas abiertas registradas en docs/contratos-integracion-iv.md §4.
_BRECHAS: dict[tuple[str, str], str] = {
    # Vacío desde la versión estable 1.0.0: B-01, B-02, B-03 y B-04 quedaron
    # corregidas. Una brecha nueva se registra aquí con su ID del documento.
}


@pytest.fixture(scope="module")
def esquema_gateway() -> dict:
    gateway_app.openapi_schema = None
    try:
        return gateway_app.openapi()
    finally:
        gateway_app.openapi_schema = None


@pytest.fixture(scope="module")
def esquemas_microservicios() -> dict[str, dict]:
    return {prefijo: app.openapi() for prefijo, app in _APP_POR_PREFIJO.items()}


# ── utilidades ──────────────────────────────────────────────────────────────


def _resolver(documento: dict, nodo: Any, profundidad: int = 0) -> Any:
    if profundidad > 20:
        return nodo
    if isinstance(nodo, dict):
        if "$ref" in nodo:
            destino: Any = documento
            for parte in nodo["$ref"][2:].split("/"):
                destino = destino[parte]
            return _resolver(documento, destino, profundidad + 1)
        return {k: _resolver(documento, v, profundidad + 1) for k, v in nodo.items()}
    if isinstance(nodo, list):
        return [_resolver(documento, v, profundidad + 1) for v in nodo]
    return nodo


def _campos(documento: dict, esquema: dict) -> tuple[set[str], set[str]]:
    """Campos y obligatorios del objeto (o del ítem si es lista)."""
    esquema = _resolver(documento, esquema)
    if esquema.get("type") == "array":
        esquema = esquema.get("items", {})
    if "anyOf" in esquema:
        esquema = next(e for e in esquema["anyOf"] if e.get("type") != "null")
    return set(esquema.get("properties", {})), set(esquema.get("required", []))


def _operacion(esquema: dict, op: OperacionMovil) -> dict | None:
    return esquema["paths"].get(op.ruta, {}).get(op.metodo)


def _operacion_microservicio(esquemas: dict[str, dict], op: OperacionMovil):
    prefijo = op.ruta.split("/")[2]
    documento = esquemas[prefijo]
    return documento, documento["paths"][op.ruta[len("/api"):]][op.metodo]


def _exitos(operacion: dict) -> dict[str, dict]:
    return {c: r for c, r in operacion["responses"].items() if c.startswith("2")}


def _estados_esperados(op: OperacionMovil, operacion: dict) -> set[str]:
    estados = {"502", "504", *op.estados_requeridos}
    if not op.publica:
        estados.add("401")
    if op.roles_rechazados:
        estados.add("403")
    parametros = [
        p for p in operacion.get("parameters", []) if p["name"] not in _CABECERAS_GATEWAY
    ]
    if any(p["in"] == "path" for p in parametros):
        estados.add("404")
    if parametros or "requestBody" in operacion:
        estados.add("422")
    return estados


# ── comprobaciones ──────────────────────────────────────────────────────────


def _comprobar(
    nombre: str,
    op: OperacionMovil,
    esquema: dict,
    esquemas_ms: dict[str, dict],
) -> list[str]:
    """Devuelve la lista de diferencias (vacía si la comprobación se cumple)."""
    operacion = _operacion(esquema, op)
    if nombre == "publicada":
        return [] if operacion is not None else ["no aparece en /openapi.json"]
    assert operacion is not None, f"{op.clave} no está publicada"

    if nombre == "seguridad":
        esquemas_bearer = {
            nombre_esquema
            for nombre_esquema, definicion in esquema["components"]
            .get("securitySchemes", {})
            .items()
            if definicion.get("type") == "http" and definicion.get("scheme") == "bearer"
        }
        tiene = any(
            set(requisito) & esquemas_bearer for requisito in operacion.get("security", [])
        )
        if op.publica and tiene:
            return ["es pública pero exige bearer"]
        if not op.publica and not tiene:
            return ["es protegida pero no declara bearer"]
        return []

    exitos = _exitos(operacion)
    if nombre == "respuesta_exito":
        con_esquema = [
            c for c, r in exitos.items() if (c == "204" and not r.get("content")) or r.get("content", {}).get(_JSON, {}).get("schema")
        ]
        return [] if con_esquema else ["sin respuesta 2xx application/json con esquema"]

    if nombre == "ejemplo_exito":
        faltan = []
        for codigo, respuesta in exitos.items():
            if codigo == "204" and not respuesta.get("content"):
                continue  # No Content no lleva JSON ni ejemplo de cuerpo.
            contenido = respuesta.get("content", {}).get(_JSON, {})
            if not (contenido.get("example") is not None or contenido.get("examples")):
                faltan.append(f"{codigo} sin ejemplo")
        return faltan

    if nombre == "estados":
        faltan = _estados_esperados(op, operacion) - set(operacion["responses"])
        return [f"no publica {c}" for c in sorted(faltan)]

    documento_ms, operacion_ms = _operacion_microservicio(esquemas_ms, op)
    if nombre == "estados_microservicio":
        faltan = set(operacion_ms["responses"]) - set(operacion["responses"])
        return [f"el microservicio declara {c} y la Gateway no" for c in sorted(faltan)]

    if nombre == "campos_microservicio":
        diferencias: list[str] = []
        param_gw = {
            (p["name"], p["in"])
            for p in operacion.get("parameters", [])
            if p["name"] not in _CABECERAS_GATEWAY
        }
        param_ms = {(p["name"], p["in"]) for p in operacion_ms.get("parameters", [])}
        if param_gw != param_ms:
            diferencias.append(f"parámetros gw={sorted(param_gw)} ms={sorted(param_ms)}")
        body_gw = operacion.get("requestBody", {}).get("content", {})
        body_ms = operacion_ms.get("requestBody", {}).get("content", {})
        if set(body_gw) != set(body_ms):
            diferencias.append(f"tipos de body gw={sorted(body_gw)} ms={sorted(body_ms)}")
        for tipo in set(body_gw) & set(body_ms):
            if _campos(esquema, body_gw[tipo]["schema"]) != _campos(
                documento_ms, body_ms[tipo]["schema"]
            ):
                diferencias.append(f"campos del body {tipo} distintos")
        for codigo, respuesta_ms in _exitos(operacion_ms).items():
            esquema_ms = respuesta_ms.get("content", {}).get(_JSON, {}).get("schema")
            esquema_gw = (
                exitos.get(codigo, {}).get("content", {}).get(_JSON, {}).get("schema")
            )
            if esquema_ms and esquema_gw and _campos(esquema, esquema_gw) != _campos(
                documento_ms, esquema_ms
            ):
                diferencias.append(f"campos de la respuesta {codigo} distintos")
        return diferencias

    raise AssertionError(f"comprobación desconocida: {nombre}")


def _casos():
    for op in OPERACIONES_INTEGRACION_IV:
        for nombre in _COMPROBACIONES:
            marcas = []
            brecha = _BRECHAS.get((op.clave, nombre))
            if brecha:
                marcas.append(pytest.mark.xfail(reason=brecha, strict=True))
            yield pytest.param(op, nombre, id=f"{op.clave}::{nombre}", marks=marcas)


@pytest.mark.parametrize(("op", "comprobacion"), _casos())
def test_contrato_movil(
    op: OperacionMovil,
    comprobacion: str,
    esquema_gateway: dict,
    esquemas_microservicios: dict[str, dict],
) -> None:
    diferencias = _comprobar(comprobacion, op, esquema_gateway, esquemas_microservicios)
    assert not diferencias, f"{op.clave} [{comprobacion}]: {diferencias}"


# ── reglas del catálogo ────────────────────────────────────────────────────


def test_catalogo_sin_duplicados() -> None:
    claves = [op.clave for op in OPERACIONES_INTEGRACION_IV]
    assert len(claves) == len(set(claves))


def test_catalogo_solo_roles_moviles() -> None:
    for op in OPERACIONES_INTEGRACION_IV:
        assert op.roles, op.clave
        assert set(op.roles) <= {CLIENTE, MECANICO}, op.clave
        assert not set(op.roles) & set(op.roles_rechazados), op.clave


def test_catalogo_solo_rutas_de_la_gateway() -> None:
    for op in OPERACIONES_INTEGRACION_IV:
        assert op.ruta.startswith("/api/"), op.clave
        assert not op.ruta.startswith("/api/health"), op.clave


def test_cada_rol_movil_tiene_su_flujo_minimo() -> None:
    """Cliente: entra, ve órdenes y decide; Mecánico: entra, trabaja y sube evidencia."""
    por_rol = {
        rol: {op.clave for op in OPERACIONES_INTEGRACION_IV if rol in op.roles}
        for rol in (CLIENTE, MECANICO)
    }
    assert {
        "POST /api/auth/login",
        "GET /api/ordenes",
        "GET /api/evidencias",
        "POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/decision",
    } <= por_rol[CLIENTE]
    assert {
        "POST /api/auth/login",
        "GET /api/ordenes",
        "PATCH /api/ordenes/{orden_id}/estado",
        "POST /api/ordenes/{orden_id}/bitacora",
        "POST /api/evidencias",
    } <= por_rol[MECANICO]
