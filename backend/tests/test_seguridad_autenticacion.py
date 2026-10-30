"""Pruebas de seguridad de autenticación: huecos aún no cubiertos.

La autorización por rol ya está probada en otras suites: el guard de MS2 en
`test_vehiculos_api.py`, el de MS3 en `test_ms3_estructura.py`, el de MS1 y el
`401`/`403` en `test_autorizacion.py`, y los endpoints de administración en
`test_usuarios_roles.py`. Este módulo añade solo lo que faltaba, sobre MS1 y MS4:

- MS1 (a nivel HTTP): token expirado, token firmado con otra clave, token de un
  usuario inexistente o inactivo y cabeceras `Authorization` mal formadas. La
  suite previa de MS1 solo probaba un token literal inválido.
- MS4: el guard `obtener_principal_actual`, que hasta ahora no tenía ninguna
  prueba ejecutable.

No reimplementa el contrato del token: usa `shared.auth` para emitir/firmar y
los guards reales de cada servicio para validar.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms1_auth.config import settings as ms1_settings
from services.ms1_auth.models.usuario import Usuario
from services.ms4_evidencias.config import settings as ms4_settings
from services.ms4_evidencias.dependencies import (
    obtener_principal_actual as obtener_principal_ms4,
)
from shared.auth import NombreRol, PrincipalAutenticado, crear_token_acceso


CLAVE_MS1 = ms1_settings.JWT_SECRET_KEY.get_secret_value()
CLAVE_MS4 = ms4_settings.JWT_SECRET_KEY.get_secret_value()
# Clave distinta a las de los servicios: simula un token de otro firmante.
CLAVE_AJENA = "clave-ajena-exclusiva-para-pruebas-1234567890"

DATOS_REGISTRO = {
    "email": "inactivo@correo.cl",
    "password": "ClaveSegura123!",
    "full_name": "Cuenta Inactiva",
}


def _firmar(payload: dict, *, clave: str) -> str:
    """Firma un payload arbitrario (para tokens expirados o manipulados)."""

    return jwt.encode(payload, clave, algorithm="HS256")


def _token_ms1(usuario_id: int, *roles: NombreRol) -> str:
    """Bearer JWT válido emitido con la clave de MS1."""

    return crear_token_acceso(
        usuario_id,
        roles or (NombreRol.CLIENTE,),
        clave_secreta=CLAVE_MS1,
        algoritmo=ms1_settings.JWT_ALGORITHM,
    )


# --------------------------------------------------------------------------- #
# MS1 — autenticación a nivel HTTP                                            #
# --------------------------------------------------------------------------- #


def test_ms1_token_expirado_devuelve_401(api: TestClient) -> None:
    token = _firmar(
        {
            "sub": "1",
            "roles": [NombreRol.CLIENTE.value],
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        clave=CLAVE_MS1,
    )

    respuesta = api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_ms1_token_firmado_con_otra_clave_devuelve_401(api: TestClient) -> None:
    token = crear_token_acceso(1, [NombreRol.CLIENTE], clave_secreta=CLAVE_AJENA)

    respuesta = api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_ms1_token_de_usuario_inexistente_devuelve_401(api: TestClient) -> None:
    respuesta = api.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {_token_ms1(999999)}"},
    )

    assert respuesta.status_code == 401


def test_ms1_token_de_usuario_inactivo_devuelve_401(
    api: TestClient, db: Session
) -> None:
    registro = api.post("/auth/register", json=DATOS_REGISTRO)
    assert registro.status_code == 201, registro.text
    usuario_id = registro.json()["id"]

    usuario = db.scalar(select(Usuario).where(Usuario.usuario_id == usuario_id))
    usuario.activo = False
    db.commit()

    respuesta = api.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {_token_ms1(usuario_id)}"},
    )

    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "cabecera",
    ["Basic dXNlcjpwYXNz", "Bearer", "Token abc"],
    ids=["esquema-basico", "bearer-sin-token", "esquema-desconocido"],
)
def test_ms1_cabecera_authorization_mal_formada_devuelve_401(
    api: TestClient, cabecera: str
) -> None:
    respuesta = api.get("/auth/me", headers={"Authorization": cabecera})

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


# --------------------------------------------------------------------------- #
# MS4 — guard de autenticación (sin endpoints de negocio todavía)             #
# --------------------------------------------------------------------------- #


def _app_ms4_protegida() -> FastAPI:
    """App mínima que solo monta el guard de MS4 para probarlo aislado."""

    prueba = FastAPI()

    @prueba.get("/recurso")
    def recurso(
        principal: PrincipalAutenticado = Depends(obtener_principal_ms4),
    ) -> dict[str, object]:
        return {
            "usuario_id": principal.usuario_id,
            "roles": sorted(rol.value for rol in principal.roles),
        }

    return prueba


def _token_ms4(usuario_id: int, *roles: NombreRol) -> str:
    return crear_token_acceso(
        usuario_id,
        roles or (NombreRol.CLIENTE,),
        clave_secreta=CLAVE_MS4,
        algoritmo=ms4_settings.JWT_ALGORITHM,
    )


def test_ms4_sin_token_devuelve_401() -> None:
    respuesta = TestClient(_app_ms4_protegida()).get("/recurso")

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_ms4_token_invalido_devuelve_401() -> None:
    respuesta = TestClient(_app_ms4_protegida()).get(
        "/recurso", headers={"Authorization": "Bearer no-es-un-jwt"}
    )

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_ms4_token_expirado_devuelve_401() -> None:
    token = _firmar(
        {
            "sub": "1",
            "roles": [NombreRol.CLIENTE.value],
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        clave=CLAVE_MS4,
    )

    respuesta = TestClient(_app_ms4_protegida()).get(
        "/recurso", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 401


def test_ms4_token_de_otro_microservicio_devuelve_401() -> None:
    """Un token firmado con la clave de MS1 no vale en MS4."""

    token = _token_ms1(1, NombreRol.CLIENTE)

    respuesta = TestClient(_app_ms4_protegida()).get(
        "/recurso", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 401


def test_ms4_token_valido_devuelve_200_con_la_identidad() -> None:
    token = _token_ms4(42, NombreRol.MECANICO)

    respuesta = TestClient(_app_ms4_protegida()).get(
        "/recurso", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"usuario_id": 42, "roles": ["mecanico"]}
