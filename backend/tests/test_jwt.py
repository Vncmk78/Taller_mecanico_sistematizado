"""Pruebas del contrato JWT común, sin FastAPI ni base de datos."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from jose import jwt

from shared.auth import (
    NombreRol,
    TokenInvalidoError,
    crear_token_acceso,
    validar_token_acceso,
)

CLAVE = "clave-secreta-exclusiva-para-pruebas-jwt-123456"


def test_token_valido_devuelve_principal_tipado():
    token = crear_token_acceso(
        42,
        [NombreRol.CLIENTE, NombreRol.MECANICO],
        clave_secreta=CLAVE,
    )

    principal = validar_token_acceso(token, clave_secreta=CLAVE)

    assert principal.usuario_id == 42
    assert principal.roles == frozenset({NombreRol.CLIENTE, NombreRol.MECANICO})


def test_token_con_firma_invalida_es_rechazado():
    token = crear_token_acceso(1, [NombreRol.CLIENTE], clave_secreta=CLAVE)

    with pytest.raises(TokenInvalidoError):
        validar_token_acceso(token, clave_secreta="otra-clave-secreta-segura-123456789")


def test_token_expirado_es_rechazado():
    token = _firmar(
        {
            "sub": "1",
            "roles": ["cliente"],
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
    )

    with pytest.raises(TokenInvalidoError):
        validar_token_acceso(token, clave_secreta=CLAVE)


@pytest.mark.parametrize(
    "payload",
    [
        {"sub": "1", "roles": ["cliente"]},
        {"roles": ["cliente"], "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        {
            "sub": str(uuid4()),
            "roles": ["cliente"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        {
            "sub": "abc",
            "roles": ["cliente"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        {"sub": "1", "roles": "cliente", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        {"sub": "1", "roles": [], "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        {
            "sub": "1",
            "roles": ["desconocido"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
    ],
    ids=[
        "sin-exp",
        "sin-sub",
        "sub-uuid",
        "sub-no-entero",
        "sin-roles",
        "roles-no-lista",
        "roles-vacia",
        "rol-desconocido",
    ],
)
def test_claims_obligatorios_y_formato(payload):
    token = _firmar(payload)

    with pytest.raises(TokenInvalidoError):
        validar_token_acceso(token, clave_secreta=CLAVE)


def _firmar(payload: dict) -> str:
    return jwt.encode(payload, CLAVE, algorithm="HS256")
