"""Casos de uso de autenticación y usuarios de MS1."""

from services.ms1_auth.services.autenticacion import (
    ConfiguracionRolesError,
    CorreoRegistradoError,
    CredencialesInvalidasError,
    autenticar_usuario,
    buscar_usuario_activo_por_id,
    registrar_cliente,
    roles_del_usuario,
)

__all__ = [
    "ConfiguracionRolesError",
    "CorreoRegistradoError",
    "CredencialesInvalidasError",
    "autenticar_usuario",
    "buscar_usuario_activo_por_id",
    "registrar_cliente",
    "roles_del_usuario",
]
