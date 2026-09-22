"""Dependencias FastAPI de autenticación y autorización de MS1."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from services.ms1_auth.config import settings
from services.ms1_auth.db import get_db
from services.ms1_auth.models.usuario import Usuario
from services.ms1_auth.services.autenticacion import (
    PersistenciaAutenticacionError,
    buscar_usuario_activo_por_id,
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
    """Extrae y valida el JWT sin consultar la base de datos de MS1."""

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


def obtener_usuario_actual(
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    db: Session = Depends(get_db),
) -> Usuario:
    """Resuelve el registro vigente de MS1 para /auth/me."""

    try:
        usuario = buscar_usuario_activo_por_id(db, principal.usuario_id)
    except PersistenciaAutenticacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar el usuario",
        ) from exc
    if usuario is None:
        raise _error_no_autenticado("Usuario no válido")
    return usuario


def requerir_roles(
    *roles_permitidos: NombreRol,
) -> Callable[[PrincipalAutenticado], PrincipalAutenticado]:
    """Crea un guard que exige al menos uno de los roles indicados."""

    if not roles_permitidos:
        raise ValueError("Debe indicarse al menos un rol permitido")
    permitidos = frozenset(roles_permitidos)

    def dependencia(
        principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    ) -> PrincipalAutenticado:
        if principal.roles.isdisjoint(permitidos):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para realizar esta operación",
            )
        return principal

    return dependencia


def _error_no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )
