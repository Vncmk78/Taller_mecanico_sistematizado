"""Dependencias de autenticación y resolución del Cliente actual en MS2."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from services.ms2_taller.config import settings
from services.ms2_taller.db import get_db
from services.ms2_taller.models.cliente import Cliente
from services.ms2_taller.services.clientes import (
    PersistenciaClienteError,
    buscar_cliente_por_usuario_id,
)
from shared.auth import (
    NombreRol,
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


def resolver_cliente_actual(
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    db: Session = Depends(get_db),
) -> Cliente:
    """Resuelve el perfil local sin crearlo ni consultar la base de MS1."""

    if NombreRol.CLIENTE not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operación",
        )

    try:
        cliente = buscar_cliente_por_usuario_id(db, principal.usuario_id)
    except PersistenciaClienteError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar el perfil de cliente",
        ) from exc

    if cliente is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario autenticado no tiene un perfil Cliente en MS2",
        )
    return cliente


def _error_no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )
