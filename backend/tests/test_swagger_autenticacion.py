"""Validar la autenticación desde Swagger UI en los endpoints protegidos.

Swagger UI no ejecuta reglas de negocio: para que el botón *Authorize* funcione
la Gateway debe publicar un esquema `http` / `bearer` / JWT y cada operación
protegida debe declararlo. Estas pruebas validan ese contrato y reproducen el
flujo que se hace en `/docs`:

1. `POST /api/auth/login` (público) devuelve `access_token`.
2. Ese valor se pega en *Authorize*; Swagger envía `Authorization: Bearer <token>`.
3. Las operaciones protegidas dejan de responder `401` y devuelven la respuesta
   del microservicio.
4. Sin *Authorize*, las mismas operaciones responden `401` con
   `WWW-Authenticate: Bearer`.

Se reutiliza el ecosistema en proceso de `test_gateway_smoke_prefijos` (Gateway
real + MS1..MS4 reales) y su catálogo de endpoints representativos. La
declaración `security` de **todas** las operaciones ya la fija
`test_gateway_openapi.py`; aquí no se duplica.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.main import app as gateway_app
from test_gateway_smoke_prefijos import (  # noqa: F401  (fixture reutilizada)
    gateway_con_microservicios,
    smoke,
)


CORREO = "swagger-auth@pruebas.cl"
CLAVE = "ClaveSwagger123!"
NOMBRE = "Prueba Swagger Auth"


@pytest.fixture
def docs() -> TestClient:
    return TestClient(gateway_app)


def _token_de_login(gw: TestClient) -> str:
    """Publica el token que un usuario copiaría en el cuadro *Authorize*."""
    registro = gw.post(
        "/api/auth/register",
        json={"email": CORREO, "password": CLAVE, "full_name": NOMBRE},
    )
    assert registro.status_code == 201, registro.text

    login = gw.post("/api/auth/login", json={"email": CORREO, "password": CLAVE})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert isinstance(token, str) and token
    return token


# --------------------------------------------------------------------------- #
# Contrato que hace aparecer el botón Authorize                                #
# --------------------------------------------------------------------------- #


def test_swagger_publica_authorize_para_jwt(docs: TestClient) -> None:
    pagina = docs.get("/docs")
    assert pagina.status_code == 200
    assert "swagger-ui" in pagina.text.lower()
    assert "/openapi.json" in pagina.text

    esquema = docs.get("/openapi.json").json()
    # `http` + `bearer` dibujan el botón Authorize; `bearerFormat` documenta
    # que el valor a pegar es un JWT (no una clave de API ni un basic).
    assert esquema["components"]["securitySchemes"]["bearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }


# --------------------------------------------------------------------------- #
# Flujo Authorize sobre operaciones protegidas                                 #
# --------------------------------------------------------------------------- #


def test_login_de_swagger_emite_un_jwt_para_authorize(
    gateway_con_microservicios,
) -> None:
    token = _token_de_login(gateway_con_microservicios)
    assert token.count(".") == 2  # cabecera.payload.firma

    respuesta = gateway_con_microservicios.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert smoke.codigo_gateway(respuesta) is None
    assert respuesta.status_code == 200, respuesta.text


@pytest.mark.parametrize("ruta", sorted(set(smoke.REPRESENTATIVOS.values())))
def test_sin_authorize_las_protegidas_devuelven_401(
    gateway_con_microservicios, ruta: str
) -> None:
    respuesta = gateway_con_microservicios.get(f"/api{ruta}")

    assert smoke.codigo_gateway(respuesta) is None  # 401 del microservicio
    assert respuesta.status_code == 401, respuesta.text
    assert "detail" in respuesta.json()
    assert respuesta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("ruta", sorted(set(smoke.REPRESENTATIVOS.values())))
def test_con_authorize_las_protegidas_no_devuelven_401(
    gateway_con_microservicios, ruta: str
) -> None:
    token = _token_de_login(gateway_con_microservicios)
    respuesta = gateway_con_microservicios.get(
        f"/api{ruta}", headers={"Authorization": f"Bearer {token}"}
    )

    assert smoke.codigo_gateway(respuesta) is None
    # 200/403/404/422 son respuestas del microservicio: el JWT fue aceptado.
    assert respuesta.status_code in {200, 403, 404, 422}, respuesta.text


def test_token_sin_el_prefijo_bearer_no_autentica(gateway_con_microservicios) -> None:
    """En Authorize se pega el token crudo: Swagger arma `Bearer <token>`.

    Si se envía directamente la cabecera con el token sin el prefijo, el
    servicio debe rechazarlo; así se comprueba que el prefijo es parte del
    contrato y no algo que los guards inventan.
    """
    token = _token_de_login(gateway_con_microservicios)
    respuesta = gateway_con_microservicios.get(
        "/api/auth/me", headers={"Authorization": token}
    )

    assert respuesta.status_code == 401, respuesta.text
    assert respuesta.headers["www-authenticate"] == "Bearer"
