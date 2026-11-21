"""Pruebas de exposición indebida de datos en respuestas HTTP.

Complementa `docs/revision-dtos-respuesta-campos-sensibles.md`: verifica que
las respuestas de MS1 no devuelvan la contraseña ni su hash, que el `422` del
registro de dispositivos no refleje el token y que el contrato publicado por la
Gateway no incluya campos de credenciales.

La autorización sobre recursos ajenos, las cabeceras y los secretos de
almacenamiento ya tienen suites propias; aquí no se duplican.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.main import app as gateway_app
from services.ms1_auth.config import settings
from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from shared.auth import NombreRol, crear_token_acceso


CLAVE = "ClaveUnicaExposicion123!"
EMAIL = "exposicion@correo.cl"
TOKEN_CORTO = "token-fcm-corto"
TOKEN_LARGO = "token-fcm-exclusivo-para-pruebas-de-exposicion-123456"


def _registrar(api: TestClient) -> int:
    respuesta = api.post(
        "/auth/register",
        json={"email": EMAIL, "password": CLAVE, "full_name": "Prueba Exposicion"},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


def _hash_en_bd(db: Session, usuario_id: int) -> str:
    usuario = db.scalar(select(Usuario).where(Usuario.usuario_id == usuario_id))
    assert usuario is not None
    return usuario.contrasena_hash


def _credenciales_ausentes(respuesta, hash_bd: str) -> None:
    assert CLAVE not in respuesta.text
    assert hash_bd not in respuesta.text


# --------------------------------------------------------------------------- #
# MS1 — credenciales en respuestas de éxito                                    #
# --------------------------------------------------------------------------- #


def test_registro_no_devuelve_contrasena_ni_hash(api: TestClient, db: Session) -> None:
    respuesta = api.post(
        "/auth/register",
        json={"email": EMAIL, "password": CLAVE, "full_name": "Prueba Exposicion"},
    )
    assert respuesta.status_code == 201, respuesta.text
    assert "password" not in respuesta.json()
    _credenciales_ausentes(respuesta, _hash_en_bd(db, respuesta.json()["id"]))


def test_login_y_me_no_devuelven_contrasena_ni_hash(
    api: TestClient, db: Session
) -> None:
    usuario_id = _registrar(api)
    hash_bd = _hash_en_bd(db, usuario_id)

    login = api.post("/auth/login", json={"email": EMAIL, "password": CLAVE})
    assert login.status_code == 200, login.text
    assert "access_token" in login.json()
    assert "password" not in login.json()
    assert "user" in login.json() and "password" not in login.json()["user"]
    _credenciales_ausentes(login, hash_bd)

    me = api.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.status_code == 200, me.text
    assert "password" not in me.json()
    _credenciales_ausentes(me, hash_bd)


def test_listado_de_usuarios_no_devuelve_hash(
    api: TestClient, db: Session
) -> None:
    usuario_id = _registrar(api)
    administrador = db.scalar(
        select(Rol).where(Rol.nombre == NombreRol.ADMINISTRADOR.value)
    )
    assert administrador is not None
    db.add(UsuarioRol(usuario_id=usuario_id, rol=administrador))
    db.commit()

    token = crear_token_acceso(
        usuario_id,
        (NombreRol.ADMINISTRADOR,),
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )
    respuesta = api.get(
        "/auth/usuarios", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 200, respuesta.text
    assert any(fila["id"] == usuario_id for fila in respuesta.json())
    _credenciales_ausentes(respuesta, _hash_en_bd(db, usuario_id))


# --------------------------------------------------------------------------- #
# MS1 — secretos reflejados en el detalle de validación                        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"token": TOKEN_CORTO, "plataforma": "android"},
        {"token": TOKEN_LARGO},
    ],
    ids=["token-invalido", "plataforma-faltante"],
)
def test_422_del_dispositivo_no_refleja_el_token(
    api: TestClient, cuerpo: dict[str, str]
) -> None:
    usuario_id = _registrar(api)
    token = crear_token_acceso(
        usuario_id,
        (NombreRol.CLIENTE,),
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )
    secreto = cuerpo["token"]

    respuesta = api.post(
        "/notificaciones/dispositivos",
        headers={"Authorization": f"Bearer {token}"},
        json=cuerpo,
    )

    assert respuesta.status_code == 422, respuesta.text
    assert secreto not in respuesta.text
    assert "***" in respuesta.text


# --------------------------------------------------------------------------- #
# Gateway — contrato publicado                                                  #
# --------------------------------------------------------------------------- #


_CAMPO_SENSIBLE = re.compile(
    r"password|contrasena|contraseña|hash|secret|secreto|token|clave|sha256|"
    r"dsn|credencial|api[_-]?key|fcm|minio|bucket",
    re.I,
)
# `access_token`/`token_type` son el propósito de `/auth/login`;
# `clave_operacion` es una clave de idempotencia del cliente, no una credencial.
_CAMPOS_PERMITIDOS = frozenset({"access_token", "token_type", "clave_operacion"})


@pytest.fixture
def esquema() -> dict:
    respuesta = TestClient(gateway_app).get("/openapi.json")
    assert respuesta.status_code == 200
    return respuesta.json()


def test_contrato_no_publica_campos_de_credenciales(esquema: dict) -> None:
    esquemas = esquema["components"]["schemas"]
    usados = set()
    for operaciones in esquema["paths"].values():
        for metodo, operacion in operaciones.items():
            if metodo not in {"get", "post", "put", "patch", "delete"}:
                continue
            for respuesta in operacion.get("responses", {}).values():
                for contenido in respuesta.get("content", {}).values():
                    referencia = contenido.get("schema", {}).get("$ref")
                    if referencia:
                        usados.add(referencia.rsplit("/", 1)[-1])

    expuestos = {}
    for nombre in usados:
        campos = [
            campo
            for campo in esquemas[nombre].get("properties", {})
            if _CAMPO_SENSIBLE.search(campo) and campo not in _CAMPOS_PERMITIDOS
        ]
        if campos:
            expuestos[nombre] = campos

    assert expuestos == {}
