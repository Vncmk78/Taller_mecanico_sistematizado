"""Pruebas de autenticación desde la plataforma web y la aplicación móvil.

La Gateway es el **único** punto de entrada para los dos clientes
(`gateway/main.py`), y ambos deben autenticarse con el mismo contrato:
`POST /auth/login` para obtener el token y `Authorization: Bearer <token>` en
las peticiones protegidas. Lo que los separa es el navegador:

- **Plataforma web**: el navegador envía `Origin` y, antes de cualquier
  petición con cabeceras propias, un *preflight* `OPTIONS`. La respuesta debe
  traer `Access-Control-Allow-Origin` o el navegador la bloquea aunque el
  backend la haya servido bien.
- **Aplicación móvil**: una petición HTTP nativa, **sin cabecera `Origin`** y
  sin preflight (no hay navegador que negocie CORS). Solo manda el `Bearer`.

Ambos canales hablan contra la Gateway, que **no valida el JWT** (lo reenvía y
lo valida el microservicio). Aquí se comprueba que la cadena Gateway → MS1 se
comporta igual en los dos casos y que el CORS no rompe ni filtra la
autenticación. MS1 se simula con `respx`, sin levantar servicios.

No reimplementa el contrato del token: usa la Gateway real y mockea únicamente
la respuesta del microservicio.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from gateway.config import settings
from gateway.main import app

# Origen permitido por `CORS_ORIGINS` (el frontend de desarrollo, Vite).
ORIGEN_WEB = "http://localhost:5173"
# Origen fuera de la lista: el navegador debe bloquear la respuesta.
ORIGEN_NO_PERMITIDO = "http://atacante.ejemplo"

TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.firma"
RUTA_MS1_LOGIN = f"{settings.MS1_URL}/auth/login"
RUTA_MS1_ME = f"{settings.MS1_URL}/auth/me"

# Cuerpo realista de MS1: el token y su tipo.
CUERPO_LOGIN_OK = {"access_token": TOKEN, "token_type": "bearer"}
# 401 normalizado de MS1 (shared.errores_auth): el mismo para ambos canales.
CUERPO_NO_AUTENTICADO = {"detail": "Correo o contraseña incorrectos"}


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


@pytest.fixture
def api_mock() -> respx.MockRouter:
    """Mock de `httpx`: cualquier petición sin ruta definida falla sola."""
    with respx.mock(assert_all_mocked=True) as mock:
        yield mock


def _cabeceras_web(peticion: str) -> dict[str, str]:
    """Cabeceras de un navegador para un *preflight* hacia `peticion`."""

    return {
        "Origin": ORIGEN_WEB,
        "Access-Control-Request-Method": peticion,
        "Access-Control-Request-Headers": "authorization,content-type",
    }


# --------------------------------------------------------------------------- #
# Plataforma web: Origin + preflight                                           #
# --------------------------------------------------------------------------- #


def test_preflight_de_login_lo_responde_la_gateway_sin_llegar_a_ms1(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    """El navegador sondea antes de enviar credenciales.

    El preflight lo contesta el middleware de CORS: no debe reenviarse a MS1
    (con `assert_all_mocked` una llamada sin mock reventaría la prueba).
    """

    respuesta = gateway.options("/api/auth/login", headers=_cabeceras_web("POST"))

    assert respuesta.status_code == 200
    assert not api_mock.calls


def test_preflight_autoriza_la_cabecera_authorization(
    gateway: TestClient,
) -> None:
    """Sin esto el navegador bloquea el `Bearer` antes de mandarlo."""

    respuesta = gateway.options("/api/auth/login", headers=_cabeceras_web("POST"))

    permitidas = respuesta.headers["access-control-allow-headers"].lower()
    assert "authorization" in permitidas


def test_login_web_lleva_access_control_allow_origin(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.post(RUTA_MS1_LOGIN).mock(
        return_value=httpx.Response(200, json=CUERPO_LOGIN_OK)
    )

    respuesta = gateway.post(
        "/api/auth/login",
        json={"email": "cliente@pruebas.cl", "password": "ClientePrueba123!"},
        headers={"Origin": ORIGEN_WEB},
    )

    assert respuesta.status_code == 200
    # Con credenciales el middleware ecoa el origen exacto, no `*`.
    assert respuesta.headers["access-control-allow-origin"] == ORIGEN_WEB
    assert respuesta.headers["access-control-allow-credentials"] == "true"
    assert respuesta.json() == CUERPO_LOGIN_OK


def test_preflight_de_origen_no_permitido_se_rechaza(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    """El CORS restringe de verdad: un origen ajeno no obtiene permiso."""

    respuesta = gateway.options(
        "/api/auth/login",
        headers={
            "Origin": ORIGEN_NO_PERMITIDO,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert respuesta.status_code == 400
    assert "access-control-allow-origin" not in respuesta.headers
    assert not api_mock.calls


def test_login_web_de_origen_no_permitido_no_recibe_allow_origin(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    """El backend responde, pero sin ACAO el navegador la bloquea."""

    api_mock.post(RUTA_MS1_LOGIN).mock(
        return_value=httpx.Response(200, json=CUERPO_LOGIN_OK)
    )

    respuesta = gateway.post(
        "/api/auth/login",
        json={"email": "cliente@pruebas.cl", "password": "ClientePrueba123!"},
        headers={"Origin": ORIGEN_NO_PERMITIDO},
    )

    assert respuesta.status_code == 200
    assert "access-control-allow-origin" not in respuesta.headers


# --------------------------------------------------------------------------- #
# Aplicación móvil: sin Origin, solo Bearer                                     #
# --------------------------------------------------------------------------- #


def test_login_movil_sin_origin_funciona_y_no_hay_preflight(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    """La app móvil no envía `Origin`: el login debe funcionar igual."""

    ruta = api_mock.post(RUTA_MS1_LOGIN).mock(
        return_value=httpx.Response(200, json=CUERPO_LOGIN_OK)
    )

    respuesta = gateway.post(
        "/api/auth/login",
        json={"email": "cliente@pruebas.cl", "password": "ClientePrueba123!"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == CUERPO_LOGIN_OK
    # Sin origen no hay nada que permitir: no debe aparecer cabecera CORS.
    assert "access-control-allow-origin" not in respuesta.headers
    # El body de credenciales llega intacto a MS1.
    assert ruta.calls.last.request.content


def test_me_movil_reenvia_el_bearer_al_microservicio(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    ruta = api_mock.get(RUTA_MS1_ME).mock(
        return_value=httpx.Response(200, json={"id": 1, "roles": ["cliente"]})
    )

    respuesta = gateway.get("/api/auth/me", headers={"Authorization": f"Bearer {TOKEN}"})

    assert respuesta.status_code == 200
    assert ruta.calls.last.request.headers["authorization"] == f"Bearer {TOKEN}"


# --------------------------------------------------------------------------- #
# Paridad entre los dos canales                                                #
# --------------------------------------------------------------------------- #


def test_me_web_reenvia_el_token_y_expone_el_request_id(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    """El navegador recibe el mismo `401`/`200` y puede leer `X-Request-ID`."""

    ruta = api_mock.get(RUTA_MS1_ME).mock(
        return_value=httpx.Response(200, json={"id": 1, "roles": ["cliente"]})
    )

    respuesta = gateway.get(
        "/api/auth/me",
        headers={"Origin": ORIGEN_WEB, "Authorization": f"Bearer {TOKEN}"},
    )

    assert respuesta.status_code == 200
    assert ruta.calls.last.request.headers["authorization"] == f"Bearer {TOKEN}"
    assert respuesta.headers["access-control-allow-origin"] == ORIGEN_WEB
    # `expose_headers=["X-Request-ID"]`: solo el navegador necesita que se le
    # autorice a leerla; la app móvil la ve sin más.
    assert respuesta.headers["x-request-id"]


def test_me_sin_token_responde_401_idéntico_en_los_dos_canales(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    """El rechazo no depende del canal ni revela de cuál vino."""

    api_mock.get(RUTA_MS1_ME).mock(
        return_value=httpx.Response(401, json={"detail": "No autenticado"})
    )

    con_origin = gateway.get("/api/auth/me", headers={"Origin": ORIGEN_WEB})
    sin_origin = gateway.get("/api/auth/me")

    assert con_origin.status_code == sin_origin.status_code == 401
    assert con_origin.json() == sin_origin.json() == {"detail": "No autenticado"}
    # El navegador también necesita CORS en el error, o vería un fallo de red.
    assert con_origin.headers["access-control-allow-origin"] == ORIGEN_WEB


def test_login_fallido_responde_igual_en_los_dos_canales(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    """Un error de credenciales se comporta igual para web y para móvil."""

    api_mock.post(RUTA_MS1_LOGIN).mock(
        return_value=httpx.Response(401, json=CUERPO_NO_AUTENTICADO)
    )
    credenciales = {"email": "cliente@pruebas.cl", "password": "Correcta123!"}

    web = gateway.post("/api/auth/login", json=credenciales, headers={"Origin": ORIGEN_WEB})
    movil = gateway.post("/api/auth/login", json=credenciales)

    assert web.status_code == movil.status_code == 401
    assert web.json() == movil.json() == CUERPO_NO_AUTENTICADO
    assert web.headers["access-control-allow-origin"] == ORIGEN_WEB
    assert "access-control-allow-origin" not in movil.headers
