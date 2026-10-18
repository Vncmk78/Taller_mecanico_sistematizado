"""Dependencias de autenticación y almacenamiento del microservicio MS4.

Reutiliza el validador puro de shared.auth (mismo contrato que MS2): MS4 valida
el Bearer JWT sin consultar la base de MS1. `obtener_principal_actual` la usan
todos los endpoints de evidencias. Los clientes S3 se exponen como dependencias
cacheadas para que los endpoints y los tests puedan reemplazarlos (override).
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.ms4_evidencias.config import settings
from services.ms4_evidencias.services.almacenamiento import (
    crear_cliente_s3,
    crear_cliente_s3_publico,
)
from shared.auth import (
    PrincipalAutenticado,
    TokenInvalidoError,
    validar_token_acceso,
)
from shared.errores_auth import error_no_autenticado

_bearer = HTTPBearer(auto_error=False)


def obtener_principal_actual(
    request: Request,
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> PrincipalAutenticado:
    """Valida el Bearer JWT mediante el contrato puro compartido.

    Deja el `usuario_id` en `request.state` para que el log de la solicitud
    (MiddlewareRegistro) sepa quién la hizo; el token nunca se guarda ahí.
    """

    if credenciales is None:
        raise error_no_autenticado()
    try:
        principal = validar_token_acceso(
            credenciales.credentials,
            clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
            algoritmo=settings.JWT_ALGORITHM,
        )
    except TokenInvalidoError as exc:
        raise error_no_autenticado() from exc
    request.state.usuario_id = principal.usuario_id
    return principal


def obtener_token_bearer(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """JWT tal como llegó: MS4 lo reenvía a MS2 para validar la orden (§8)."""
    if credenciales is None:
        raise error_no_autenticado()
    return credenciales.credentials


@lru_cache
def obtener_s3() -> object:
    """Cliente S3 interno (subir, borrar y verificar el bucket)."""
    return crear_cliente_s3(settings)


@lru_cache
def obtener_s3_publico() -> object:
    """Cliente S3 que firma URLs de descarga con el endpoint que ve el cliente."""
    return crear_cliente_s3_publico(settings)


__all__ = [
    "obtener_principal_actual",
    "obtener_token_bearer",
    "obtener_s3",
    "obtener_s3_publico",
]
