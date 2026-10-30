"""Normalización de las respuestas `401` y `403` de autenticación/autorización.

Toda la lógica vive en `shared.errores_auth` (fuente única de verdad de la
forma de la respuesta). Este módulo comprueba que los cuatro microservicios la
usan y que el resultado es uniforme:

- el `401` de cualquier causa (token ausente, mal formado, inválido o
  expirado) sale con el **mismo** cuerpo `{"detail": "No autenticado"}` y la
  cabecera `WWW-Authenticate: Bearer`;
- el `403` de cualquier guard de rol sale con el **mismo** cuerpo
  `{"detail": "No tienes permiso para realizar esta operación"}`.

No reimplementa los guards: monta los reales de cada microservicio en una app
mínima, sin base de datos.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from services.ms1_auth.config import settings as ms1_settings
from services.ms1_auth.dependencies import (
    obtener_principal_actual as principal_ms1,
)
from services.ms1_auth.dependencies import requerir_roles as roles_ms1
from services.ms2_taller.dependencies import (
    obtener_principal_actual as principal_ms2,
)
from services.ms3_presupuestos.config import settings as ms3_settings
from services.ms3_presupuestos.dependencies import (
    obtener_principal_actual as principal_ms3,
)
from services.ms3_presupuestos.dependencies import requerir_roles as roles_ms3
from services.ms4_evidencias.dependencies import (
    obtener_principal_actual as principal_ms4,
)
from shared.auth import NombreRol, PrincipalAutenticado, crear_token_acceso
from shared.errores_auth import (
    NO_AUTENTICADO,
    SIN_PERMISO,
    error_no_autenticado,
    error_sin_permiso,
)

# Guards de autenticación reales de los cuatro microservicios.
GUARDAS_401 = {
    "ms1": principal_ms1,
    "ms2": principal_ms2,
    "ms3": principal_ms3,
    "ms4": principal_ms4,
}

CUERPO_401 = {"detail": NO_AUTENTICADO}
CUERPO_403 = {"detail": SIN_PERMISO}

DATOS_REGISTRO = {
    "email": "normalizacion@correo.cl",
    "password": "ClaveSegura123!",
    "full_name": "Cuenta Normalización",
}


def _app_con(guarda) -> FastAPI:
    """App mínima que monta un guard real de un microservicio."""

    prueba = FastAPI()

    @prueba.get("/recurso")
    def recurso(principal: PrincipalAutenticado = Depends(guarda)) -> dict[str, int]:
        return {"usuario_id": principal.usuario_id}

    return prueba


def _bearer_token(settings, usuario_id: int, *roles: NombreRol) -> str:
    return crear_token_acceso(
        usuario_id,
        roles,
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )


# --------------------------------------------------------------------------- #
# Helper compartido: fuente única de verdad                                   #
# --------------------------------------------------------------------------- #


def test_helper_401_tiene_mensaje_unico_y_cabecera() -> None:
    error = error_no_autenticado()

    assert error.status_code == 401
    assert error.detail == NO_AUTENTICADO
    assert error.headers == {"WWW-Authenticate": "Bearer"}


def test_helper_403_tiene_mensaje_unico() -> None:
    error = error_sin_permiso()

    assert error.status_code == 403
    assert error.detail == SIN_PERMISO
    assert error.headers is None


# --------------------------------------------------------------------------- #
# 401 — mismo cuerpo en los cuatro microservicios                            #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("nombre", sorted(GUARDAS_401))
def test_401_sin_token_es_uniforme_en_todos_los_servicios(nombre: str) -> None:
    respuesta = TestClient(_app_con(GUARDAS_401[nombre])).get("/recurso")

    assert respuesta.status_code == 401
    assert respuesta.json() == CUERPO_401
    assert respuesta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("nombre", sorted(GUARDAS_401))
def test_401_token_invalido_es_identico_al_de_sin_token(nombre: str) -> None:
    respuesta = TestClient(_app_con(GUARDAS_401[nombre])).get(
        "/recurso", headers={"Authorization": "Bearer no-es-un-jwt"}
    )

    assert respuesta.status_code == 401
    assert respuesta.json() == CUERPO_401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_ms1_login_con_credenciales_invalidas_lleva_cabecera_y_su_mensaje(
    api: TestClient,
) -> None:
    assert api.post("/auth/register", json=DATOS_REGISTRO).status_code == 201

    respuesta = api.post(
        "/auth/login",
        json={"email": DATOS_REGISTRO["email"], "password": "incorrecta"},
    )

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
    assert respuesta.json() == {"detail": "Correo o contraseña incorrectos"}


def test_ms1_login_no_enumera_usuarios(api: TestClient) -> None:
    assert api.post("/auth/register", json=DATOS_REGISTRO).status_code == 201

    inexistente = api.post(
        "/auth/login", json={"email": "nadie@correo.cl", "password": "incorrecta"}
    )
    incorrecta = api.post(
        "/auth/login",
        json={"email": DATOS_REGISTRO["email"], "password": "incorrecta"},
    )

    assert inexistente.status_code == incorrecta.status_code == 401
    assert inexistente.json() == incorrecta.json()


# --------------------------------------------------------------------------- #
# 403 — mismo cuerpo en los guards de rol                                     #
# --------------------------------------------------------------------------- #


def test_403_ms1_rol_insuficiente_tiene_cuerpo_unico() -> None:
    guarda = roles_ms1(NombreRol.ADMINISTRADOR)
    token = _bearer_token(ms1_settings, 5, NombreRol.CLIENTE)

    respuesta = TestClient(_app_con(guarda)).get(
        "/recurso", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 403
    assert respuesta.json() == CUERPO_403


def test_403_ms3_rol_insuficiente_tiene_el_mismo_cuerpo() -> None:
    guarda = roles_ms3(NombreRol.ADMINISTRADOR)
    token = _bearer_token(ms3_settings, 5, NombreRol.CLIENTE)

    respuesta = TestClient(_app_con(guarda)).get(
        "/recurso", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 403
    assert respuesta.json() == CUERPO_403
