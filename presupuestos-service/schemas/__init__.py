"""Contratos HTTP de MS1."""

from services.ms1_auth.schemas.auth import (
    LoginSolicitud,
    RegistroClienteSolicitud,
    TokenRespuesta,
    UsuarioRespuesta,
)

__all__ = [
    "LoginSolicitud",
    "RegistroClienteSolicitud",
    "TokenRespuesta",
    "UsuarioRespuesta",
]
