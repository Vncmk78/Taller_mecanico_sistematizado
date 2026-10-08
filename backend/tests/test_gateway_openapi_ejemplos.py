"""Pruebas de los ejemplos y respuestas comunes del OpenAPI de la Gateway.

Verifican que `/openapi.json` sigue siendo un OpenAPI válido, que todos los
ejemplos son reales (cumplen el esquema que los acompaña, no traen URLs internas
ni tokens reales, y los errores de la Gateway usan los mensajes del catálogo) y
que `gateway/openapi_ejemplos.py` es idempotente y no pisa los ejemplos de órdenes
que ya documenta `shared/openapi_ordenes.py`.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate as validar_openapi

from gateway.errores import (
    MENSAJE_CUERPO_DEMASIADO_GRANDE,
    MENSAJE_ERROR_MICROSERVICIO,
    MENSAJE_GATEWAY_SATURADA,
    MENSAJE_METODO_NO_PERMITIDO,
    MENSAJE_RUTA_NO_ENCONTRADA,
    MENSAJE_SERVICIO_CAIDO,
    MENSAJE_TIEMPO_AGOTADO,
)
from gateway.errores import _MENSAJE_ERROR_INTERNO as MENSAJE_ERROR_INTERNO
from gateway.main import app
from gateway.openapi_ejemplos import agregar_ejemplos_gateway
from gateway.rutas import RUTAS

_METODOS = ("get", "post", "put", "patch", "delete")
_JSON = "application/json"

# Ningún token real puede publicarse en el esquema: solo estos dos, ambos de
# ejemplo (el del contrato y el de la respuesta de login).
_TOKENS_PERMITIDOS = {
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "eyJhbGciOiJIUzI1NiJ9.ejemplo.firma",
}

# Los ocho errores de la Gateway: ejemplo -> (código, estado, detalle).
_ERRORES_GATEWAY = {
    "error_ruta_no_encontrada": ("RUTA_NO_ENCONTRADA", 404, MENSAJE_RUTA_NO_ENCONTRADA),
    "error_metodo_no_permitido": (
        "METODO_NO_PERMITIDO",
        405,
        MENSAJE_METODO_NO_PERMITIDO,
    ),
    "error_microservicio_no_disponible": (
        "MICROSERVICIO_INALCANZABLE",
        502,
        MENSAJE_SERVICIO_CAIDO,
    ),
    "error_gateway_saturada": ("GATEWAY_SATURADA", 503, MENSAJE_GATEWAY_SATURADA),
    "error_tiempo_agotado": ("TIEMPO_AGOTADO", 504, MENSAJE_TIEMPO_AGOTADO),
    "error_microservicio": (
        "ERROR_MICROSERVICIO",
        500,
        MENSAJE_ERROR_MICROSERVICIO,
    ),
    "error_interno_gateway": ("ERROR_INTERNO", 500, MENSAJE_ERROR_INTERNO),
    "error_cuerpo_demasiado_grande": (
        "CUERPO_DEMASIADO_GRANDE",
        413,
        MENSAJE_CUERPO_DEMASIADO_GRANDE,
    ),
}

# MS4 responde su propio 503 (almacenamiento o MS2 caídos) además del de la
# Gateway; esas operaciones no usan la respuesta reutilizable GatewaySaturada.
_OPERACIONES_EVIDENCIAS = {
    ("/api/evidencias", "post"),
    ("/api/evidencias", "get"),
    ("/api/evidencias/{evidencia_id}", "get"),
    ("/api/evidencias/{evidencia_id}/descarga", "get"),
}


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


@pytest.fixture
def esquema(gateway: TestClient) -> dict:
    """Esquema recién construido (la app lo cachea en `openapi_schema`)."""
    app.openapi_schema = None
    try:
        documento = gateway.get("/openapi.json")
        assert documento.status_code == 200
        return documento.json()
    finally:
        app.openapi_schema = None


def _operaciones_de_negocio(esquema: dict) -> dict[tuple[str, str], dict]:
    return {
        (ruta, metodo): operacion
        for ruta, item in esquema["paths"].items()
        for metodo in _METODOS
        if (operacion := item.get(metodo)) is not None
        if ruta.startswith("/api/") and not ruta.startswith("/api/health")
    }


def _destino(esquema: dict, referencia: str) -> Any:
    assert referencia.startswith("#/"), referencia
    nodo: Any = esquema
    for parte in referencia[2:].split("/"):
        nodo = nodo[parte]
    return nodo


def _resolver(nodo: Any, esquema: dict, profundidad: int = 0) -> Any:
    """Devuelve el esquema con sus `$ref` locales ya resueltos."""
    if profundidad > 20:
        return {}
    if isinstance(nodo, dict):
        if "$ref" in nodo:
            hermanos = {clave: v for clave, v in nodo.items() if clave != "$ref"}
            return _resolver(
                {**_destino(esquema, nodo["$ref"]), **hermanos}, esquema, profundidad + 1
            )
        return {
            clave: _resolver(valor, esquema, profundidad + 1)
            for clave, valor in nodo.items()
        }
    if isinstance(nodo, list):
        return [_resolver(valor, esquema, profundidad + 1) for valor in nodo]
    return nodo


def _valida_contra_esquema(valor: Any, esquema_resuelto: dict, etiqueta: str) -> None:
    """Valida un ejemplo contra su esquema, tolerando el `oneOf` de errores.

    El documento usa `oneOf` para las respuestas que pueden venir de la Gateway o
    de un microservicio (`ErrorRespuesta` y `ErrorDetalle`). Un cuerpo de la
    Gateway cumple ambos, así que se acepta que case con alguna de las variantes.
    """
    if not list(Draft202012Validator(esquema_resuelto).iter_errors(valor)):
        return
    if "oneOf" in esquema_resuelto:
        for alternativa in esquema_resuelto["oneOf"]:
            if not list(Draft202012Validator(alternativa).iter_errors(valor)):
                return
    pytest.fail(f"El ejemplo de {etiqueta} no cumple su esquema: {valor!r}")


def _medias_con_ejemplos(esquema: dict) -> list[tuple[str, dict, dict]]:
    """[(etiqueta, media type, ejemplo)] de todo el documento."""
    encontrados: list[tuple[str, dict, dict]] = []

    def revisar_media(media: dict, etiqueta: str) -> None:
        for nombre, ejemplo in media.get("examples", {}).items():
            referencia = ejemplo.get("$ref") if isinstance(ejemplo, dict) else None
            valor = _destino(esquema, referencia) if referencia else ejemplo
            assert isinstance(valor, dict) and "value" in valor, f"{etiqueta}/{nombre}"
            encontrados.append((f"{etiqueta}/{nombre}", media, valor["value"]))

    for ruta, item in esquema["paths"].items():
        for metodo, operacion in item.items():
            if metodo not in _METODOS:
                continue
            etiqueta = f"{metodo.upper()} {ruta}"
            cuerpo = operacion.get("requestBody", {}).get("content", {})
            if _JSON in cuerpo:
                revisar_media(cuerpo[_JSON], f"{etiqueta} (body)")
            for codigo, respuesta in operacion["responses"].items():
                if "$ref" in respuesta:
                    respuesta = _destino(esquema, respuesta["$ref"])
                contenido = respuesta.get("content", {})
                if _JSON in contenido:
                    revisar_media(contenido[_JSON], f"{etiqueta} {codigo}")

    for nombre, respuesta in esquema.get("components", {}).get("responses", {}).items():
        contenido = respuesta.get("content", {})
        if _JSON in contenido:
            revisar_media(contenido[_JSON], f"components.responses.{nombre}")
    return encontrados


def _textos(nodo: Any) -> list[str]:
    if isinstance(nodo, dict):
        return [texto for valor in nodo.values() for texto in _textos(valor)]
    if isinstance(nodo, list):
        return [texto for valor in nodo for texto in _textos(valor)]
    return [nodo] if isinstance(nodo, str) else []


def test_openapi_cumple_el_especificador(esquema: dict) -> None:
    validar_openapi(esquema)


def test_todos_los_ejemplos_cumplen_su_esquema(esquema: dict) -> None:
    ejemplos = _medias_con_ejemplos(esquema)
    assert len(ejemplos) > 40, "faltaría la mayoría de los ejemplos"
    for etiqueta, media, valor in ejemplos:
        _valida_contra_esquema(valor, _resolver(media.get("schema", {}), esquema), etiqueta)


def test_los_errores_de_la_gateway_usan_el_catalogo_de_mensajes(esquema: dict) -> None:
    ejemplos = esquema["components"]["examples"]
    for nombre, (codigo, estado, detalle) in _ERRORES_GATEWAY.items():
        valor = ejemplos[nombre]["value"]
        assert valor["detail"] == detalle, nombre
        assert valor["error"] == {
            "codigo": codigo,
            "estado": estado,
            "ruta": valor["error"]["ruta"],
            "request_id": valor["error"]["request_id"],
        }, nombre
        assert valor["error"]["ruta"].startswith("/api/"), nombre


@pytest.mark.parametrize("nombre", sorted(_ERRORES_GATEWAY))
def test_los_errores_de_la_gateway_se_publican_como_ejemplos(esquema: dict, nombre: str) -> None:
    ejemplos = esquema["components"]["examples"]
    assert "summary" in ejemplos[nombre]
    assert "description" in ejemplos[nombre]


def test_las_respuestas_reutilizables_declaran_su_contrato(esquema: dict) -> None:
    respuestas = esquema["components"]["responses"]
    assert set(respuestas) == {
        "NoAutenticado",
        "ErrorInterno",
        "ServicioNoDisponible",
        "GatewaySaturada",
        "TiempoAgotado",
    }
    assert "WWW-Authenticate" in respuestas["NoAutenticado"]["headers"]
    assert "Retry-After" in respuestas["GatewaySaturada"]["headers"]
    for nombre, respuesta in respuestas.items():
        assert "X-Request-ID" in respuesta["headers"], nombre
        assert respuesta["content"][_JSON]["examples"], nombre


def test_las_operaciones_de_negocio_documentan_las_respuestas_comunes(
    esquema: dict,
) -> None:
    operaciones = _operaciones_de_negocio(esquema)
    assert set(operaciones) == {
        ("/api/auth/login", "post"),
        ("/api/auth/me", "get"),
        ("/api/auth/register", "post"),
        ("/api/ordenes", "get"),
        ("/api/ordenes", "post"),
        ("/api/ordenes/{orden_id}", "get"),
        ("/api/ordenes/{orden_id}/estado", "patch"),
        ("/api/ordenes/{orden_id}/decisiones-presupuesto", "post"),
        ("/api/presupuestos/decisiones/{decision_id}", "get"),
        ("/api/presupuestos/decisiones/{decision_id}/aplicacion", "post"),
        ("/api/ordenes/{orden_id}/historial", "get"),
        ("/api/ordenes/{orden_id}/mecanico", "put"),
        ("/api/vehiculos", "get"),
        ("/api/vehiculos", "post"),
        ("/api/vehiculos/asignados", "get"),
        ("/api/vehiculos/{vehiculo_id}", "get"),
        ("/api/vehiculos/{vehiculo_id}", "patch"),
    } | _OPERACIONES_EVIDENCIAS
    for (ruta, metodo), operacion in operaciones.items():
        respuestas = operacion["responses"]
        etiqueta = f"{metodo.upper()} {ruta}"
        for codigo in ("404", "500", "502", "503", "504"):
            assert codigo in respuestas, f"{etiqueta} sin {codigo}"
        if (ruta, metodo) in _OPERACIONES_EVIDENCIAS:
            esquema_503 = respuestas["503"]["content"][_JSON]["schema"]
            assert {item["$ref"] for item in esquema_503["oneOf"]} == {
                "#/components/schemas/ErrorRespuesta",
                "#/components/schemas/ErrorDetalle",
            }, etiqueta
            assert {
                "almacenamiento_no_disponible",
                "ordenes_no_disponible",
                "gateway_saturada",
            } <= set(respuestas["503"]["content"][_JSON]["examples"]), etiqueta
        elif ruta in {"/api/ordenes/{orden_id}/decisiones-presupuesto",
                      "/api/presupuestos/decisiones/{decision_id}/aplicacion"}:
            refs = respuestas["503"]["content"][_JSON]["schema"]["oneOf"]
            assert {item["$ref"] for item in refs} >= {"#/components/schemas/ErrorRespuesta"}
        else:
            assert respuestas["503"] == {"$ref": "#/components/responses/GatewaySaturada"}
        assert respuestas["504"] == {"$ref": "#/components/responses/TiempoAgotado"}
        # El registro es público; el login responde 401 por credenciales, no por
        # token ausente, y el resto de operaciones exige Bearer.
        if ruta == "/api/auth/register":
            assert "401" not in respuestas
        else:
            assert "401" in respuestas, etiqueta


def test_los_ejemplos_de_autenticacion_y_vehiculos_cubren_los_cuerpos(
    esquema: dict,
) -> None:
    for (ruta, metodo), operacion in _operaciones_de_negocio(esquema).items():
        if ruta.startswith("/api/ordenes"):
            continue  # los documenta shared/openapi_ordenes.py
        etiqueta = f"{metodo.upper()} {ruta}"
        cuerpo = operacion.get("requestBody", {}).get("content", {}).get(_JSON, {})
        if cuerpo:
            assert cuerpo.get("examples"), f"{etiqueta} sin ejemplo de body"
        respuesta_exito = "201" if "201" in operacion["responses"] else "200"
        ejemplos = operacion["responses"][respuesta_exito]["content"][_JSON]
        assert ejemplos.get("examples"), f"{etiqueta} {respuesta_exito} sin ejemplo"


def test_los_ejemplos_de_ordenes_no_se_pisan(esquema: dict) -> None:
    ordenes = esquema["paths"]["/api/ordenes"]["post"]["responses"]
    ejemplos = ordenes["201"]["content"][_JSON]["examples"]
    assert ejemplos["recibido"]["value"]["estado_codigo"] == 1
    assert ejemplos["recibido"]["value"]["mecanico_actual_id"] is None
    assert "sin_token" in ordenes["401"]["content"][_JSON]["examples"]
    # Los ejemplos comunes se agregan sin eliminar los de órdenes.
    assert {"token_ausente", "token_invalido"} <= set(
        ordenes["401"]["content"][_JSON]["examples"]
    )


def test_health_documenta_servicios_ok_y_degradado(esquema: dict) -> None:
    salud = esquema["paths"]["/api/health"]["get"]["responses"]["200"]
    assert salud["content"][_JSON]["examples"]["gateway_viva"]["value"] == {
        "status": "ok",
        "servicio": "gateway",
    }

    servicios = esquema["paths"]["/api/health/servicios"]["get"]["responses"]
    assert set(servicios) >= {"200", "503"}
    ok = servicios["200"]["content"][_JSON]["examples"]["servicios_ok"]["value"]
    assert ok["status"] == "ok"
    assert set(ok["servicios"]) == {
        "ms1_auth",
        "ms2_taller",
        "ms3_presupuestos",
        "ms4_evidencias",
    }
    assert all(servicio["estado"] == "ok" for servicio in ok["servicios"].values())
    degradado = servicios["503"]["content"][_JSON]["examples"][
        "servicios_degradados"
    ]["value"]
    assert degradado["status"] == "degradado"
    assert degradado["servicios"]["ms3_presupuestos"]["estado"] == "caido"
    assert degradado["servicios"]["ms4_evidencias"]["estado"] == "sin_base"


def test_toda_respuesta_de_api_declara_x_request_id(esquema: dict) -> None:
    for ruta, item in esquema["paths"].items():
        if not ruta.startswith("/api"):
            continue
        for metodo, operacion in item.items():
            if metodo not in _METODOS:
                continue
            for codigo, respuesta in operacion["responses"].items():
                if "$ref" in respuesta:
                    respuesta = _destino(esquema, respuesta["$ref"])
                assert "X-Request-ID" in respuesta.get("headers", {}), (
                    f"{metodo.upper()} {ruta} {codigo}"
                )


def test_no_se_publican_urls_internas_ni_tokens_reales(esquema: dict) -> None:
    documento = json.dumps(esquema, ensure_ascii=False)
    assert "localhost" not in documento
    for url in set(RUTAS.values()):
        assert url not in documento, url
    tokens = {texto for texto in _textos(esquema) if texto.startswith("eyJ")}
    assert tokens <= _TOKENS_PERMITIDOS, tokens - _TOKENS_PERMITIDOS


def test_agregar_ejemplos_gateway_es_idempotente(esquema: dict) -> None:
    antes = json.dumps(esquema, sort_keys=True, ensure_ascii=False)
    agregar_ejemplos_gateway(esquema)
    agregar_ejemplos_gateway(esquema)
    assert json.dumps(esquema, sort_keys=True, ensure_ascii=False) == antes

def test_401_de_operaciones_protegidas_documenta_www_authenticate() -> None:
    """Cada 401 de una operación con bearerAuth documenta WWW-Authenticate.

    MS1 y MS2 responden `WWW-Authenticate: Bearer` y la Gateway lo reenvía.
    """
    from gateway.main import app

    app.openapi_schema = None
    esquema = app.openapi()
    revisadas = 0
    for ruta, item in esquema["paths"].items():
        for metodo, op in item.items():
            if not isinstance(op, dict) or not op.get("security"):
                continue
            respuesta_401 = op["responses"]["401"]
            if "$ref" in respuesta_401:
                nombre = respuesta_401["$ref"].rsplit("/", 1)[-1]
                respuesta_401 = esquema["components"]["responses"][nombre]
            assert "WWW-Authenticate" in respuesta_401.get("headers", {}), (metodo, ruta)
            assert "X-Request-ID" in respuesta_401.get("headers", {}), (metodo, ruta)
            revisadas += 1
    assert revisadas >= 8
