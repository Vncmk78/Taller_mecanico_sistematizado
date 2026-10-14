"""Pruebas del enrutamiento de la API Gateway.

Simulan MS1 y MS2 (Semana 1) y MS3 y MS4 (Semana 4) con `respx` (sin
levantarlos): la Gateway reenvía hacia la URL correcta conservando método,
body, query string y las cabeceras Authorization y X-Request-ID, incluida la
subida multipart con su content-type completo (boundary incluido).
"""
from __future__ import annotations

import json
import uuid

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from gateway.config import settings
from gateway.errores import MENSAJE_SERVICIO_CAIDO, MICROSERVICIO_INALCANZABLE
from gateway.main import app
from gateway.rutas import resolver_microservicio


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


@pytest.fixture
def api_mock() -> respx.MockRouter:
    """Mock de `httpx`: cualquier petición sin ruta definida falla sola."""
    with respx.mock(assert_all_mocked=True) as mock:
        yield mock


@pytest.mark.parametrize("metodo,ruta,servicio,body", [
    ("POST", "ordenes/31/decisiones-presupuesto", "MS2_URL", {"decision_id": 9}),
    ("GET", "presupuestos/decisiones/9", "MS3_URL", None),
    ("POST", "presupuestos/decisiones/9/aplicacion", "MS3_URL", None),
])
def test_coordinacion_decisiones_preserva_ruta_body_y_jwt(
    gateway: TestClient, api_mock: respx.MockRouter,
    metodo: str, ruta: str, servicio: str, body: dict | None,
) -> None:
    destino = api_mock.request(metodo, f"{getattr(settings, servicio)}/{ruta}").mock(
        return_value=httpx.Response(200, json={"decision_id": 9}),
    )
    argumentos = {"json": body} if body is not None else {}
    respuesta = gateway.request(metodo, f"/api/{ruta}",
                                headers={"Authorization": "Bearer jwt-original"}, **argumentos)
    assert respuesta.status_code == 200
    solicitud = destino.calls.last.request
    assert solicitud.headers["authorization"] == "Bearer jwt-original"
    assert str(solicitud.url) == f"{getattr(settings, servicio)}/{ruta}"
    if body is not None:
        assert json.loads(solicitud.content) == body


def test_verificacion_propiedad_preserva_query_y_jwt(gateway, api_mock):
    destino = api_mock.get(f"{settings.MS2_URL}/ordenes/31?solo_propietario=true").mock(
        return_value=httpx.Response(200, json={"orden_id": 31}),
    )
    respuesta = gateway.get("/api/ordenes/31?solo_propietario=true",
                            headers={"Authorization": "Bearer jwt-original"})
    assert respuesta.status_code == 200
    solicitud = destino.calls.last.request
    assert solicitud.url.params["solo_propietario"] == "true"
    assert solicitud.headers["authorization"] == "Bearer jwt-original"


def test_auth_login_reenvia_a_ms1_con_su_body(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.post(f"{settings.MS1_URL}/auth/login").mock(
        return_value=httpx.Response(200, json={"token": "abc.def.ghi"})
    )

    respuesta = gateway.post("/api/auth/login", json={"usuario": "admin", "clave": "1234"})

    assert respuesta.status_code == 200
    assert ruta.called
    llamada = ruta.calls.last.request
    assert str(llamada.url) == f"{settings.MS1_URL}/auth/login"
    assert json.loads(llamada.content.decode()) == {"usuario": "admin", "clave": "1234"}


def test_authorization_llega_al_microservicio(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.get(f"{settings.MS1_URL}/auth/me").mock(
        return_value=httpx.Response(200, json={"usuario": "admin"})
    )

    respuesta = gateway.get("/api/auth/me", headers={"Authorization": "Bearer token.jwt.abc"})

    assert respuesta.status_code == 200
    assert ruta.calls.last.request.headers["authorization"] == "Bearer token.jwt.abc"


def test_vehiculos_reenvia_a_ms2(gateway: TestClient, api_mock: respx.MockRouter) -> None:
    ruta = api_mock.get(f"{settings.MS2_URL}/vehiculos")

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 200
    assert str(ruta.calls.last.request.url) == f"{settings.MS2_URL}/vehiculos"


def test_query_string_se_mantiene(gateway: TestClient, api_mock: respx.MockRouter) -> None:
    ruta = api_mock.get(f"{settings.MS2_URL}/vehiculos", params={"patente": "AB1234"})

    respuesta = gateway.get("/api/vehiculos", params={"patente": "AB1234"})

    assert respuesta.status_code == 200
    assert ruta.calls.last.request.url.params["patente"] == "AB1234"


def test_patch_preserva_metodo_y_sub_path(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.patch(f"{settings.MS2_URL}/vehiculos/5")

    respuesta = gateway.patch("/api/vehiculos/5", json={"estado": "en_revision"})

    assert respuesta.status_code == 200
    assert ruta.calls.last.request.method == "PATCH"
    assert str(ruta.calls.last.request.url) == f"{settings.MS2_URL}/vehiculos/5"


@pytest.mark.parametrize("prefijo", ["ordenes", "orden", "clientes", "mecanicos"])
def test_rutas_de_ordenes_llegan_a_ms2(
    gateway: TestClient, api_mock: respx.MockRouter, prefijo: str
) -> None:
    ruta = api_mock.get(f"{settings.MS2_URL}/{prefijo}")

    respuesta = gateway.get(f"/api/{prefijo}")

    assert respuesta.status_code == 200
    assert ruta.called


def test_respuesta_del_microservicio_no_se_altera(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    cuerpo = {"detail": "Token inválido o expirado"}
    api_mock.get(f"{settings.MS1_URL}/auth/me").mock(
        return_value=httpx.Response(401, json=cuerpo)
    )

    respuesta = gateway.get("/api/auth/me")

    assert respuesta.status_code == 401
    assert respuesta.json() == cuerpo


def test_prefijo_desconocido_devuelve_404_sin_llamar_ms(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    respuesta = gateway.get("/api/desconocido")

    assert respuesta.status_code == 404
    assert api_mock.calls == []


def test_microservicio_caido_devuelve_502(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.post(f"{settings.MS1_URL}/auth/login").mock(
        side_effect=httpx.ConnectError("MS1 caído")
    )

    respuesta = gateway.post("/api/auth/login", json={"usuario": "admin"})

    assert respuesta.status_code == 502


def test_presupuestos_5_reenvia_a_ms3(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.get(f"{settings.MS3_URL}/presupuestos/5")

    respuesta = gateway.get("/api/presupuestos/5")

    assert respuesta.status_code == 200
    assert str(ruta.calls.last.request.url) == f"{settings.MS3_URL}/presupuestos/5"


@pytest.mark.parametrize("prefijo", ["repuestos", "proveedores", "inventario"])
def test_demas_prefijos_de_presupuestos_llegan_a_ms3(
    gateway: TestClient, api_mock: respx.MockRouter, prefijo: str
) -> None:
    ruta = api_mock.get(f"{settings.MS3_URL}/{prefijo}")

    respuesta = gateway.get(f"/api/{prefijo}")

    assert respuesta.status_code == 200
    assert ruta.called


def test_evidencias_con_orden_id_llega_a_ms4_con_su_query(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.get(f"{settings.MS4_URL}/evidencias", params={"orden_id": "7"})

    respuesta = gateway.get("/api/evidencias", params={"orden_id": 7})

    assert respuesta.status_code == 200
    assert str(ruta.calls.last.request.url) == f"{settings.MS4_URL}/evidencias?orden_id=7"


def test_post_multipart_de_evidencia_llega_a_ms4_con_mismos_bytes(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    contenido_archivo = b"\xff\xd8\xff\xe1" + b"\x00" * 32
    peticion_original = httpx.Request(
        "POST",
        f"{settings.MS4_URL}/evidencias",
        files={"archivo": ("foto.jpg", contenido_archivo, "image/jpeg")},
    )
    cuerpo_esperado = peticion_original.read()
    content_type_esperado = peticion_original.headers["content-type"]
    assert content_type_esperado.startswith("multipart/form-data; boundary=")

    peticiones: list[httpx.Request] = []

    def capturar(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        return httpx.Response(200)

    api_mock.post(f"{settings.MS4_URL}/evidencias").mock(side_effect=capturar)

    respuesta = gateway.post(
        "/api/evidencias",
        content=cuerpo_esperado,
        headers={"content-type": content_type_esperado},
    )

    assert respuesta.status_code == 200
    assert len(peticiones) == 1
    reenviada = peticiones[0]
    assert str(reenviada.url) == f"{settings.MS4_URL}/evidencias"
    assert reenviada.content == cuerpo_esperado
    assert reenviada.headers["content-type"] == content_type_esperado


@pytest.mark.parametrize(
    ("prefijo", "base"),
    [("presupuestos", settings.MS3_URL), ("evidencias", settings.MS4_URL)],
)
def test_authorization_y_x_request_id_llegan_a_ms3_y_ms4(
    gateway: TestClient, api_mock: respx.MockRouter, prefijo: str, base: str
) -> None:
    ruta = api_mock.get(f"{base}/{prefijo}")

    respuesta = gateway.get(
        f"/api/{prefijo}",
        headers={
            "Authorization": "Bearer token.jwt.xyz",
            "X-Request-ID": "abc-123-9f0e",
        },
    )

    assert respuesta.status_code == 200
    llamada = ruta.calls.last.request
    assert llamada.headers["authorization"] == "Bearer token.jwt.xyz"
    assert llamada.headers["x-request-id"] == "abc-123-9f0e"


@pytest.mark.parametrize(
    ("prefijo", "base"),
    [("presupuestos", settings.MS3_URL), ("evidencias", settings.MS4_URL)],
)
def test_ms3_o_ms4_caido_devuelve_502_con_formato_comun(
    gateway: TestClient, api_mock: respx.MockRouter, prefijo: str, base: str
) -> None:
    api_mock.get(f"{base}/{prefijo}").mock(
        side_effect=httpx.ConnectError("servicio caído")
    )

    respuesta = gateway.get(f"/api/{prefijo}")

    assert respuesta.status_code == 502
    cuerpo = respuesta.json()
    assert cuerpo["detail"] == MENSAJE_SERVICIO_CAIDO
    assert cuerpo["error"]["codigo"] == MICROSERVICIO_INALCANZABLE
    assert cuerpo["error"]["estado"] == 502
    assert cuerpo["error"]["ruta"] == f"/api/{prefijo}"
    assert uuid.UUID(cuerpo["error"]["request_id"])
    assert respuesta.headers["x-request-id"] == cuerpo["error"]["request_id"]


@pytest.mark.parametrize(
    ("ruta", "esperado"),
    [
        ("auth/login", settings.MS1_URL),
        ("vehiculos", settings.MS2_URL),
        ("vehiculos/5", settings.MS2_URL),
        ("ordenes", settings.MS2_URL),
        ("clientes", settings.MS2_URL),
        ("MECANICOS", settings.MS2_URL),
        ("presupuestos", settings.MS3_URL),
        ("presupuestos/5", settings.MS3_URL),
        ("repuestos", settings.MS3_URL),
        ("proveedores", settings.MS3_URL),
        ("inventario", settings.MS3_URL),
        ("evidencias", settings.MS4_URL),
        ("evidencia", settings.MS4_URL),
        # La trampa de la convención: MS4 vive bajo /evidencias, nunca bajo
        # /ordenes/...; un endpoint así resolvería a MS2, no a MS4.
        ("ordenes/1/evidencias", settings.MS2_URL),
        ("desconocido", None),
    ],
)
def test_resolver_microservicio(ruta: str, esperado: str | None) -> None:
    assert resolver_microservicio(ruta) == esperado


def test_historial_reenvia_ruta_completa_y_authorization(
    gateway: TestClient, api_mock: respx.MockRouter,
) -> None:
    registros = [{
        "historial_id": 1, "orden_id": 31, "estado_anterior": None,
        "estado_nuevo": 1, "actor_usuario_id": 99,
        "fecha_hora": "2026-10-07T10:00:00-03:00",
        "origen": "usuario", "observacion": None,
    }]
    ruta = api_mock.get(f"{settings.MS2_URL}/ordenes/31/historial").mock(
        return_value=httpx.Response(200, json=registros),
    )
    respuesta = gateway.get(
        "/api/ordenes/31/historial",
        headers={"Authorization": "Bearer token.jwt.historial"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == registros
    llamada = ruta.calls.last.request
    assert llamada.method == "GET"
    assert str(llamada.url) == f"{settings.MS2_URL}/ordenes/31/historial"
    assert llamada.headers["authorization"] == "Bearer token.jwt.historial"
