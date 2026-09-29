"""Copias de los contratos HTTP de MS1 (Autenticación) para la documentación.

La Gateway no importa código de los microservicios (eso rompería el
aislamiento entre servicios): mantiene sus propias copias para que `/docs`
funcione sin depender de que MS1 esté levantado. `tests/test_gateway_openapi.py`
compara estas copias con los esquemas reales de MS1 y avisa si se desactualizan.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Mismos valores oficiales que `shared.auth.NombreRol`, documentados sin
# importar código de los microservicios.
Rol = Literal["cliente", "mecanico", "administrador"]

_EJEMPLO_REGISTRO: dict[str, object] = {
    "email": "ana@correo.cl",
    "password": "clave-segura-123",
    "full_name": "Ana Pérez",
}

_EJEMPLO_LOGIN: dict[str, object] = {
    "email": "ana@correo.cl",
    "password": "clave-segura-123",
}

_EJEMPLO_USUARIO: dict[str, object] = {
    "id": 7,
    "email": "ana@correo.cl",
    "full_name": "Ana Pérez",
    "roles": ["cliente"],
    "is_active": True,
}

_EJEMPLO_TOKEN: dict[str, object] = {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
        "id": 7,
        "email": "ana@correo.cl",
        "full_name": "Ana Pérez",
        "roles": ["cliente"],
        "is_active": True,
    },
}


class RegistroSolicitud(BaseModel):
    """Registro público de un cliente; el rol Cliente se asigna en el servidor."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_REGISTRO]},
    )

    email: str = Field(
        description="Correo del usuario, en formato válido.",
        examples=["ana@correo.cl"],
        json_schema_extra={"format": "email"},
    )
    password: str = Field(
        description="Contraseña de al menos 8 caracteres.",
        min_length=8,
        examples=["clave-segura-123"],
    )
    full_name: str = Field(
        description="Nombre completo del usuario.",
        min_length=2,
        max_length=120,
        examples=["Ana Pérez"],
    )


class LoginSolicitud(BaseModel):
    """Credenciales para autenticarse y obtener el token de acceso."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_LOGIN]},
    )

    email: str = Field(
        description="Correo del usuario.",
        examples=["ana@correo.cl"],
        json_schema_extra={"format": "email"},
    )
    password: str = Field(
        description="Contraseña del usuario.",
        examples=["clave-segura-123"],
    )


class UsuarioRespuesta(BaseModel):
    """Representación de un usuario expuesta por la API."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EJEMPLO_USUARIO]})

    id: int = Field(description="Identificador interno del usuario.", examples=[7])
    email: str = Field(description="Correo del usuario.", examples=["ana@correo.cl"])
    full_name: str = Field(description="Nombre completo.", examples=["Ana Pérez"])
    roles: list[Rol] = Field(
        description="Roles del usuario (cliente, mecanico o administrador).",
        examples=[["cliente"]],
    )
    is_active: bool = Field(description="Si la cuenta está activa.", examples=[True])


class TokenRespuesta(BaseModel):
    """Resultado del login: token de acceso y datos del usuario."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EJEMPLO_TOKEN]})

    access_token: str = Field(
        description="JWT que se envía como `Authorization: Bearer <token>`.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    token_type: str = Field(default="bearer", description="Tipo de token.")
    user: UsuarioRespuesta = Field(description="Usuario autenticado.")