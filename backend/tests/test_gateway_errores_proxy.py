"""Pruebas del mapeo de errores y cabeceras del proxy (Semana 4, tarea 3).

Verifican las decisiones 1 a 6 de `docs/estudio-httpx-proxy.md`: timeouts por
fase, mapeo de fallos de red (`ConnectError` → 502, `Read/WriteTimeout` →
504, `PoolTimeout` → 503), reenvío tal cual de los errores JSON del
microservicio, normalización de los no-JSON, filtrado de cabeceras hacia el
cliente y propagación de `X-Forwarded-*`.
"""
from __future__ import annotations

import asyncio
import gzip
import uuid

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import gateway.cliente_http as cliente_http
from gateway.cliente_http import obtener_cliente, timeout_para
from gateway.config import settings
from gateway.errores import (
    ERROR_MICROSERVICIO,
    GATEWAY_SATURADA,
    MENSAJE_ERROR_MICROSERVICIO,
    MENSAJE_GATEWAY_SATURADA,
    MENSAJE_SERVICIO_CAIDO,
    MENSAJE_TIEMPO_AGOTADO,
    MICROSERVICIO_INALCANZABLE,
    RUTA_NO_ENCONTRADA,
    TIEMPO_AGOTADO,
    mapear_error_httpx,
)
from gateway.main import app


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


@pytest.fixture
def api_mock() -> respx.MockRouter:
    """Mock de `httpx`: cualquier petición sin ruta definida falla sola."""
    with respx.mock(assert_all_mocked=True) as mock:
        yield mock


@pytest.fixture(autouse=True)
def cliente_http_sin_estado() -> None:
    """Descarta el cliente compartido entre tests.

    Cada caso crea el suyo dentro de su propio event loop (TestClient sin
    `with`) y contexto de respx; así no se arrastra estado de un test a otro.
    """
    yield
    cliente_http.reset_cliente()


def _request_id_valido(cuerpo: dict) -> str:
    request_id = cuerpo["error"]["request_id"]
    assert uuid.UUID(request_id)
    return request_id


# ---------------------------------------------------------------------------
# Fallos de red del proxy: mapeo de excepciones de HTTPX (decisiones 1 y 2).
# ---------------------------------------------------------------------------


def test_connect_error_mapea_502_sin_detalles_internos(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        side_effect=httpx.ConnectError("connection refused: 10.0.0.5")
    )

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 502
    cuerpo = respuesta.json()
    assert cuerpo["detail"] == MENSAJE_SERVICIO_CAIDO
    assert cuerpo["error"]["codigo"] == MICROSERVICIO_INALCANZABLE
    assert cuerpo["error"]["estado"] == 502
    # El mensaje no filtra la URL interna ni el texto de la excepción.
    assert "http://" not in respuesta.text
    assert "localhost" not in respuesta.text
    assert _request_id_valido(cuerpo)
    assert respuesta.headers["x-request-id"] == cuerpo["error"]["request_id"]
    assert cuerpo["error"]["ruta"] == "/api/vehiculos"


@pytest.mark.parametrize(
    ("exc", "estado", "codigo", "detalle"),
    [
        (
            httpx.ConnectTimeout("el host no contesta"),
            502,
            MICROSERVICIO_INALCANZABLE,
            MENSAJE_SERVICIO_CAIDO,
        ),
        (
            httpx.ReadTimeout("no envía bloques"),
            504,
            TIEMPO_AGOTADO,
            MENSAJE_TIEMPO_AGOTADO,
        ),
        (
            httpx.WriteTimeout("la subida no avanza"),
            504,
            TIEMPO_AGOTADO,
            MENSAJE_TIEMPO_AGOTADO,
        ),
        (
            httpx.PoolTimeout("pool lleno"),
            503,
            GATEWAY_SATURADA,
            MENSAJE_GATEWAY_SATURADA,
        ),
    ],
)
def test_fallos_de_red_mapean_estado_codigo_y_trazabilidad(
    gateway: TestClient,
    api_mock: respx.MockRouter,
    exc: httpx.RequestError,
    estado: int,
    codigo: str,
    detalle: str,
) -> None:
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(side_effect=exc)

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == estado
    cuerpo = respuesta.json()
    assert cuerpo["detail"] == detalle
    assert cuerpo["error"]["codigo"] == codigo
    assert cuerpo["error"]["estado"] == estado
    assert cuerpo["error"]["ruta"] == "/api/vehiculos"
    assert _request_id_valido(cuerpo)
    assert respuesta.headers["x-request-id"] == cuerpo["error"]["request_id"]


# ---------------------------------------------------------------------------
# Errores del microservicio (decisión 3): JSON tal cual, no-JSON normalizado.
# ---------------------------------------------------------------------------


def test_401_json_del_ms_con_www_authenticate_pasa_tal_cual(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    cuerpo = {"detail": "Token inválido o expirado"}
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(
            401,
            json=cuerpo,
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )
    )

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 401
    assert respuesta.json() == cuerpo
    assert respuesta.headers["www-authenticate"] == 'Bearer error="invalid_token"'


def test_422_json_en_lista_del_ms_pasa_tal_cual(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    cuerpo = {
        "detail": [
            {
                "loc": ["body", "marca"],
                "msg": "field required",
                "type": "value_error.missing",
            }
        ]
    }
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(422, json=cuerpo)
    )

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 422
    assert respuesta.json() == cuerpo


def test_500_en_texto_plano_se_normaliza_con_error_microservicio(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(
            500, text="Internal Server Error", headers={"content-type": "text/plain"}
        )
    )

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["detail"] == MENSAJE_ERROR_MICROSERVICIO
    assert cuerpo["error"]["codigo"] == ERROR_MICROSERVICIO
    assert cuerpo["error"]["estado"] == 500
    assert "Internal Server Error" not in respuesta.text


def test_502_con_html_se_normaliza_con_error_microservicio(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(
            502,
            text="<html><body>Bad Gateway</body></html>",
            headers={"content-type": "text/html"},
        )
    )

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 502
    cuerpo = respuesta.json()
    assert cuerpo["error"]["codigo"] == ERROR_MICROSERVICIO
    assert "<html>" not in respuesta.text


def test_404_no_json_del_ms_usa_ruta_no_encontrada(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 404
    cuerpo = respuesta.json()
    assert cuerpo["error"]["codigo"] == RUTA_NO_ENCONTRADA
    assert cuerpo["detail"] == "Ruta no encontrada"


# ---------------------------------------------------------------------------
# Cabeceras hacia el cliente (decisión 6): se reenvían todas las útiles.
# ---------------------------------------------------------------------------


def test_cabeceras_utiles_de_respuesta_200_llegan_al_cliente(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.get(f"{settings.MS4_URL}/evidencias").mock(
        return_value=httpx.Response(
            200,
            content=b"bytes-de-la-foto",
            headers={
                "Content-Type": "image/jpeg",
                "Content-Disposition": 'attachment; filename="foto.jpg"',
                "Cache-Control": "private, max-age=60",
                "Location": f"{settings.MS4_URL}/descargar/1",
            },
        )
    )

    respuesta = gateway.get("/api/evidencias")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-disposition"] == 'attachment; filename="foto.jpg"'
    assert respuesta.headers["cache-control"] == "private, max-age=60"
    # El Location interno se traduce a la URL pública de la Gateway (no se
    # filtra la red interna).
    assert respuesta.headers["location"] == "http://testserver/api/descargar/1"
    assert settings.MS4_URL not in respuesta.headers["location"]


def test_cabeceras_que_no_se_reenvian_al_cliente(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(
            200,
            content=gzip.compress(b"[1,2,3]"),
            headers={
                "Content-Type": "application/json",
                "Content-Encoding": "gzip",
                "Access-Control-Allow-Origin": "*",
                "X-Request-ID": "otro",
                "Server": "uvicorn",
            },
        )
    )

    respuesta = gateway.get("/api/vehiculos", headers={"X-Request-ID": "abc-123"})

    assert respuesta.status_code == 200
    assert "access-control-allow-origin" not in respuesta.headers
    assert "content-encoding" not in respuesta.headers
    assert "server" not in respuesta.headers
    # El X-Request-ID es el de la Gateway (el suyo, no el del microservicio).
    assert respuesta.headers["x-request-id"] == "abc-123"


def test_dos_set_cookie_del_ms_llegan_ambas_al_cliente(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(
            200,
            json={},
            headers=[
                ("Set-Cookie", "sesion=a; Path=/"),
                ("Set-Cookie", "preferencias=b; Path=/"),
            ],
        )
    )

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 200
    set_cookie = [v for k, v in respuesta.headers.multi_items() if k == "set-cookie"]
    assert set_cookie == ["sesion=a; Path=/", "preferencias=b; Path=/"]


def test_204_sin_body_se_reenvia_sin_cuerpo(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(204)
    )

    respuesta = gateway.get("/api/vehiculos")

    assert respuesta.status_code == 204


# ---------------------------------------------------------------------------
# Cabeceras hacia el microservicio: X-Forwarded-* (decisión 6).
# ---------------------------------------------------------------------------


def test_x_forwarded_for_proto_y_host_llegan_al_microservicio(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    peticiones: list[httpx.Request] = []

    def capturar(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        return httpx.Response(200, json={})

    api_mock.get(f"{settings.MS2_URL}/vehiculos").mock(side_effect=capturar)

    respuesta = gateway.get(
        "/api/vehiculos",
        headers={"Host": "mi-dominio.cl", "X-Forwarded-For": "203.0.113.9"},
    )

    assert respuesta.status_code == 200
    reenviada = peticiones[0]
    # El X-Forwarded-For entrante se conserva y se le concatena la IP real.
    assert reenviada.headers["x-forwarded-for"] == "203.0.113.9, testclient"
    assert reenviada.headers["x-forwarded-proto"] == "http"
    assert reenviada.headers["x-forwarded-host"] == "mi-dominio.cl"


# ---------------------------------------------------------------------------
# Cliente compartido y timeouts por fase (decisiones 1 y 4).
# ---------------------------------------------------------------------------


def test_timeout_para_evidencias_usa_timeout_de_archivos() -> None:
    assert timeout_para("evidencias").read == 60.0
    assert timeout_para("evidencias").write == 60.0
    assert timeout_para("vehiculos").read == 15.0
    assert timeout_para("vehiculos").write == 15.0
    assert timeout_para("vehiculos").connect == 3.0
    assert timeout_para("vehiculos").pool == 5.0


@pytest.mark.parametrize(
    ("exc", "esperado"),
    [
        (
            httpx.ConnectError("no conecta"),
            (502, MICROSERVICIO_INALCANZABLE, MENSAJE_SERVICIO_CAIDO),
        ),
        (
            httpx.ConnectTimeout("lento"),
            (502, MICROSERVICIO_INALCANZABLE, MENSAJE_SERVICIO_CAIDO),
        ),
        (
            httpx.ReadTimeout("no responde"),
            (504, TIEMPO_AGOTADO, MENSAJE_TIEMPO_AGOTADO),
        ),
        (
            httpx.WriteTimeout("no envía"),
            (504, TIEMPO_AGOTADO, MENSAJE_TIEMPO_AGOTADO),
        ),
        (
            httpx.PoolTimeout("pool lleno"),
            (503, GATEWAY_SATURADA, MENSAJE_GATEWAY_SATURADA),
        ),
        # Cualquier otro RequestError cae en 502 (p. ej. ProxyError).
        (
            httpx.ProxyError("proxy caído"),
            (502, MICROSERVICIO_INALCANZABLE, MENSAJE_SERVICIO_CAIDO),
        ),
    ],
)
def test_mapear_error_httpx(
    exc: httpx.RequestError, esperado: tuple[int, str, str]
) -> None:
    assert mapear_error_httpx(exc) == esperado


def test_obtener_cliente_reutiliza_dentro_del_mismo_loop() -> None:
    async def confirmar() -> None:
        primero = obtener_cliente()
        segundo = obtener_cliente()
        assert primero is segundo

    asyncio.run(confirmar())


@pytest.mark.parametrize(
    ("location", "esperado"),
    [
        ("{base}/vehiculos", "http://testserver/api/vehiculos"),
        ("{base}/vehiculos/7?x=1", "http://testserver/api/vehiculos/7?x=1"),
        ("/vehiculos/7", "http://testserver/api/vehiculos/7"),
        ("https://externo.cl/ruta", "https://externo.cl/ruta"),
    ],
)
def test_location_de_redireccion_se_traduce_a_la_gateway(
    gateway: TestClient, api_mock: respx.MockRouter, location: str, esperado: str
) -> None:
    api_mock.get(f"{settings.MS2_URL}/vehiculos/").mock(
        return_value=httpx.Response(
            307, headers={"Location": location.format(base=settings.MS2_URL)}
        )
    )
    respuesta = gateway.get("/api/vehiculos/", follow_redirects=False)
    assert respuesta.status_code == 307
    assert respuesta.headers["location"] == esperado


def test_limites_del_pool_se_aplican_en_el_transporte() -> None:
    """Con un transporte propio, HTTPX ignora el `limits=` del cliente."""
    import asyncio

    from gateway.cliente_http import obtener_cliente

    async def _pool():
        return obtener_cliente()._transport._pool

    pool = asyncio.run(_pool())
    assert pool._max_connections == 100
    assert pool._max_keepalive_connections == 20
