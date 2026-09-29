"""Dependencias de autenticación del microservicio MS4.

Reutiliza el validador puro de shared.auth (mismo contrato que MS2): MS4 valida
el Bearer JWT sin consultar la base de MS1. Por ahora `obtener_principal_actual`
quedó LISTA pero ningún endpoint la usa; la consumen los endpoints de recepción
y consulta de evidencias una vez definidos (tarea "Implementar base para
recepción y consulta", que además le suma los filtros de visibilidad por rol).
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.ms4_evidencias.config import settings
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
