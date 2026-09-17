"""Schemas HTTP para registro, login y consulta del usuario autenticado."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from shared.auth import NombreRol


class RegistroClienteSolicitud(BaseModel):
    """Registro público: el rol Cliente se asigna en el servidor."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=120)


class LoginSolicitud(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: EmailStr
    password: str


class UsuarioRespuesta(BaseModel):
    id: int
    email: str
    full_name: str
    roles: list[NombreRol]
    is_active: bool


class TokenRespuesta(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UsuarioRespuesta
