"""Pruebas de integridad del JWT: firma alterada, claims faltantes y malformado.

`shared.auth.validar_token_acceso` es la fuente única que decide si un token es
aceptable (firma, expiración y claims obligatorios). Aquí se lo ataca desde
`GET /auth/me` de MS1, el endpoint real protegido por ese guard:

- **firma alterada**: se toca la firma después de emitir el token, o se altera
  el payload dejando la firma original (intento de escalar `roles`);
- **claims faltantes**: tokens firmados con la clave correcta pero sin `sub`,
  `exp` ni `roles`;
- **token malformado**: segmentos de menos, base64 inválido y el ataque del
  algoritmo `none`.

Ningún caso debe autenticar: todos responden `401` con el cuerpo normalizado y
`WWW-Authenticate: Bearer`. Las pruebas que registran una cuenta existen para
que una regresión termine en `200` y no en un `401` engañoso (el usuario de
prueba sí está en la base).

No reimplementa el contrato: emite los tokens con `shared.auth` y los valida el
guard real de MS1.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from services.ms1_auth.config import settings as ms1_settings
from shared.auth import NombreRol, crear_token_acceso
from shared.errores_auth import NO_AUTENTICADO

CLAVE_MS1 = ms1_settings.JWT_SECRET_KEY.get_secret_value()
ALGORITMO = ms1_settings.JWT_ALGORITHM

CUERPO_401 = {"detail": NO_AUTENTICADO}

DATOS_REGISTRO = {
    "email": "integridad@correo.cl",
    "password": "ClaveSegura123!",
    "full_name": "Cuenta Integridad",
}


def _b64url(datos: bytes) -> str:
    """Codifica bytes como base64url sin relleno, como hace un JWT."""

    return base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")


def _token_ms1(usuario_id: int) -> str:
    """JWT válido de cliente emitido con la clave de MS1."""

    return crear_token_acceso(
        usuario_id,
        [NombreRol.CLIENTE],
        clave_secreta=CLAVE_MS1,
        algoritmo=ALGORITMO,
    )


def _registrar(api: TestClient) -> int:
    """Crea una cuenta real: si el ataque llegara a autenticar, responde 200."""

    respuesta = api.post("/auth/register", json=DATOS_REGISTRO)
    assert respuesta.status_code == 201, respuesta.text
    return int(respuesta.json()["id"])


def _pedir_con(api: TestClient, token: str):
    """`GET /auth/me` presentando el token indicado."""

    return api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def _alterar_payload(token: str, **cambios: object) -> str:
    """Reemplaza claims del payload conservando la firma original (sin re-firmar)."""

    header, payload, firma = token.split(".")
    decodificado = json.loads(
        base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    )
    decodificado.update(cambios)
    alterado = _b64url(json.dumps(decodificado, separators=(",", ":")).encode())
    return f"{header}.{alterado}.{firma}"


def _token_algoritmo_none(usuario_id: int) -> str:
    """Cabecera `alg: none` con firma vacía apuntando a una cuenta real."""

    cabecera = _b64url(
        json.dumps({"alg": "none", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    caducidad = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    cuerpo = _b64url(
        json.dumps(
            {
                "sub": str(usuario_id),
                "roles": [NombreRol.ADMINISTRADOR.value],
                "exp": caducidad,
            },
            separators=(",", ":"),
        ).encode()
    )
    return f"{cabecera}.{cuerpo}."


# --------------------------------------------------------------------------- #
# Firma alterada                                                              #
# --------------------------------------------------------------------------- #


def test_token_con_firma_alterada_devuelve_401(api: TestClient) -> None:
    usuario_id = _registrar(api)
    cabecera, cuerpo, firma = _token_ms1(usuario_id).split(".")
    firma_alterada = ("B" if firma[0] == "A" else "A") + firma[1:]

    respuesta = _pedir_con(api, f"{cabecera}.{cuerpo}.{firma_alterada}")

    assert respuesta.status_code == 401
    assert respuesta.json() == CUERPO_401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_payload_alterado_con_firma_original_devuelve_401(
    api: TestClient,
) -> None:
    """Cambiar `roles` sin re-firmar no debe autenticar ni escalar privilegios."""

    usuario_id = _registrar(api)
    manipulado = _alterar_payload(
        _token_ms1(usuario_id),
        roles=[NombreRol.ADMINISTRADOR.value],
    )

    respuesta = _pedir_con(api, manipulado)

    assert respuesta.status_code == 401
    assert respuesta.json() == CUERPO_401
    assert respuesta.headers["www-authenticate"] == "Bearer"


# --------------------------------------------------------------------------- #
# Claims faltantes                                                            #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "claim_a_quitar",
    ["sub", "exp", "roles"],
    ids=["sin-sub", "sin-exp", "sin-roles"],
)
def test_claim_obligatorio_faltante_devuelve_401(
    api: TestClient,
    claim_a_quitar: str,
) -> None:
    """Firma correcta con la clave correcta, pero el contrato exige los tres claims."""

    usuario_id = _registrar(api)
    payload: dict[str, object] = {
        "sub": str(usuario_id),
        "roles": [NombreRol.CLIENTE.value],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    del payload[claim_a_quitar]
    token = jwt.encode(payload, CLAVE_MS1, algorithm=ALGORITMO)

    respuesta = _pedir_con(api, token)

    assert respuesta.status_code == 401
    assert respuesta.json() == CUERPO_401
    assert respuesta.headers["www-authenticate"] == "Bearer"


# --------------------------------------------------------------------------- #
# Token malformado                                                            #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("", id="vacio"),
        pytest.param("abc", id="un-segmento"),
        pytest.param("abc.def", id="dos-segmentos"),
        pytest.param("a.b.c", id="tres-segmentos-no-json"),
        pytest.param("###.###.###", id="base64-invalido"),
        pytest.param("a.b.%%%", id="firma-basura"),
    ],
)
def test_token_malformado_devuelve_401(api: TestClient, token: str) -> None:
    respuesta = _pedir_con(api, token)

    assert respuesta.status_code == 401
    assert respuesta.json() == CUERPO_401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_token_de_algoritmo_none_devuelve_401(api: TestClient) -> None:
    """El ataque `alg: none` no debe autenticar ni apuntar a una cuenta real."""

    usuario_id = _registrar(api)

    respuesta = _pedir_con(api, _token_algoritmo_none(usuario_id))

    assert respuesta.status_code == 401
    assert respuesta.json() == CUERPO_401
    assert respuesta.headers["www-authenticate"] == "Bearer"
