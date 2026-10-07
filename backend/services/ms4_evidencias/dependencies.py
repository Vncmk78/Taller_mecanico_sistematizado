"""Dependencias de autenticación y almacenamiento del microservicio MS4.

Reutiliza el validador puro de shared.auth (mismo contrato que MS2): MS4 valida
el Bearer JWT sin consultar la base de MS1. `obtener_principal_actual` la usan
todos los endpoints de evidencias. Los clientes S3 se exponen como dependencias
cacheadas para que los endpoints y los tests puedan reemplazarlos (override).
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
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

_bearer = HTTPBearer(auto_error=False)


def obtener_principal_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> PrincipalAutenticado:
    """Valida el Bearer JWT mediante el contrato puro compartido."""

    if credenciales is None:
        raise _error_no_autenticado("No se proporcionó un token de acceso")
    try:
        return validar_token_acceso(
            credenciales.credentials,
            clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
            algoritmo=settings.JWT_ALGORITHM,
        )
    except TokenInvalidoError as exc:
        raise _error_no_autenticado("Token inválido o expirado") from exc


def _error_no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


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
    "obtener_s3",
    "obtener_s3_publico",
]
