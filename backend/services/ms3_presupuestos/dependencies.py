"""Dependencias de autenticación y autorización del microservicio MS3.

Reutiliza el validador puro de shared.auth (mismo contrato que MS2 y MS4): MS3
valida el Bearer JWT SIN consultar la base de MS1 (§8). Los endpoints de
presupuestos, repuestos, proveedores e inventario se protegen así:

    @router.get("", dependencies=[Depends(requerir_roles(NombreRol.ADMINISTRADOR))])

o, si el endpoint necesita saber quién llama:

    def endpoint(principal: PrincipalAutenticado = Depends(obtener_principal_actual)):
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.ms3_presupuestos.config import settings
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
    """Valida el Bearer JWT y devuelve la identidad (usuario_id y roles)."""

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


def requerir_roles(
    *roles_permitidos: NombreRol,
) -> Callable[[PrincipalAutenticado], PrincipalAutenticado]:
    """Crea un guard que exige al menos uno de los roles indicados (403 si no)."""

    permitidos = frozenset(roles_permitidos)

    def dependencia(
        principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    ) -> PrincipalAutenticado:
        if not permitidos & principal.roles:
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
