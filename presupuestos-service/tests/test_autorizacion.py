"""Pruebas HTTP del Bearer token y el guard multirol."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from services.ms1_auth.config import settings
from services.ms1_auth.dependencies import requerir_roles
from shared.auth import NombreRol, PrincipalAutenticado, crear_token_acceso

app_guard = FastAPI()


@app_guard.get("/solo-clientes")
def solo_clientes(
    principal: PrincipalAutenticado = Depends(requerir_roles(NombreRol.CLIENTE)),
):
    return {"usuario_id": principal.usuario_id}


cliente_guard = TestClient(app_guard)


def test_token_ausente_devuelve_401():
    respuesta = cliente_guard.get("/solo-clientes")

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_cliente_es_permitido():
    respuesta = _consultar_con_roles(NombreRol.CLIENTE)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"usuario_id": 7}


def test_mecanico_sin_cliente_recibe_403():
    respuesta = _consultar_con_roles(NombreRol.MECANICO)

    assert respuesta.status_code == 403


def test_administrador_sin_cliente_recibe_403():
    respuesta = _consultar_con_roles(NombreRol.ADMINISTRADOR)

    assert respuesta.status_code == 403


def test_multirol_incluyendo_cliente_es_permitido():
    respuesta = _consultar_con_roles(NombreRol.MECANICO, NombreRol.CLIENTE)

    assert respuesta.status_code == 200


def test_token_invalido_devuelve_401():
    respuesta = cliente_guard.get(
        "/solo-clientes",
        headers={"Authorization": "Bearer token-invalido"},
    )

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def _consultar_con_roles(*roles: NombreRol):
    token = crear_token_acceso(
        7,
        roles,
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )
    return cliente_guard.get(
        "/solo-clientes",
        headers={"Authorization": f"Bearer {token}"},
    )
