"""Pruebas de registro, login y consulta del usuario autenticado."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from services.ms1_auth.security.passwords import verificar_contrasena
from shared.auth import NombreRol


DATOS_REGISTRO = {
    "email": "ana@example.com",
    "password": "ClaveSegura123!",
    "full_name": "Ana Pérez",
}


def test_registro_publico_asigna_exclusivamente_cliente(
    api: TestClient,
    db: Session,
):
    respuesta = api.post("/auth/register", json=DATOS_REGISTRO)

    assert respuesta.status_code == 201
    assert respuesta.json()["roles"] == ["cliente"]

    usuario = db.scalar(
        select(Usuario).options(
            selectinload(Usuario.roles).selectinload(UsuarioRol.rol)
        )
    )
    assert usuario is not None
    assert usuario.contrasena_hash != DATOS_REGISTRO["password"]
    assert verificar_contrasena(DATOS_REGISTRO["password"], usuario.contrasena_hash)
    assert [asignacion.rol.nombre for asignacion in usuario.roles] == ["cliente"]


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("role", "mecanico"),
        ("role", "administrador"),
        ("roles", ["mecanico"]),
        ("roles", ["administrador"]),
    ],
)
def test_registro_publico_no_permite_elegir_roles(
    api: TestClient,
    campo: str,
    valor: object,
):
    body = {**DATOS_REGISTRO, campo: valor}

    respuesta = api.post("/auth/register", json=body)

    assert respuesta.status_code == 422


def test_login_emite_jwt_y_me_devuelve_usuario(api: TestClient):
    assert api.post("/auth/register", json=DATOS_REGISTRO).status_code == 201

    login = api.post(
        "/auth/login",
        json={
            "email": DATOS_REGISTRO["email"],
            "password": DATOS_REGISTRO["password"],
        },
    )

    assert login.status_code == 200
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["roles"] == ["cliente"]

    me = api.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == body["user"]["id"]
    assert me.json()["roles"] == ["cliente"]


def test_login_incluye_multiples_roles(api: TestClient, db: Session):
    registro = api.post("/auth/register", json=DATOS_REGISTRO)
    usuario_id = registro.json()["id"]
    rol_mecanico = db.scalar(select(Rol).where(Rol.nombre == NombreRol.MECANICO.value))
    db.add(UsuarioRol(usuario_id=usuario_id, rol=rol_mecanico))
    db.commit()

    login = api.post(
        "/auth/login",
        json={
            "email": DATOS_REGISTRO["email"],
            "password": DATOS_REGISTRO["password"],
        },
    )

    assert login.status_code == 200
    assert login.json()["user"]["roles"] == ["cliente", "mecanico"]


def test_me_sin_token_devuelve_401(api: TestClient):
    respuesta = api.get("/auth/me")

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
