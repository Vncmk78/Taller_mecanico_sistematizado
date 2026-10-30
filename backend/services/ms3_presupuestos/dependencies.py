"""Dependencias de autenticación y autorización del microservicio MS3.

Reutiliza el validador puro de shared.auth (mismo contrato que MS2 y MS4): MS3
valida el Bearer JWT SIN consultar la base de MS1 (§8). Los endpoints de
presupuestos, repuestos, proveedores e inventario se protegen así:

    @router.get("", dependencies=[Depends(requerir_roles(NombreRol.ADMINISTRADOR))])

o, si el endpoint necesita saber quién llama:

    def endpoint(principal: PrincipalAutenticado = Depends(obtener_principal_actual)):

Para acceder a datos, el endpoint pide la unidad de trabajo (una sesión por
petición, cerrada siempre por get_db) y delega en services:

    def endpoint(uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)):
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from shared.auth import (
    NombreRol,
    PrincipalAutenticado,
    TokenInvalidoError,
    validar_token_acceso,
)
from shared.errores_auth import error_no_autenticado, error_sin_permiso

_bearer = HTTPBearer(auto_error=False)


def obtener_principal_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> PrincipalAutenticado:
    """Valida el Bearer JWT y devuelve la identidad (usuario_id y roles)."""

    if credenciales is None:
        raise error_no_autenticado()
    try:
        return validar_token_acceso(
            credenciales.credentials,
            clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
            algoritmo=settings.JWT_ALGORITHM,
        )
    except TokenInvalidoError as exc:
        raise error_no_autenticado() from exc


def obtener_token_bearer(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """JWT tal como llegó: MS3 lo reenvía a MS2 para validar la orden (§8)."""
    if credenciales is None:
        raise error_no_autenticado()
    return credenciales.credentials


def requerir_roles(
    *roles_permitidos: NombreRol,
) -> Callable[[PrincipalAutenticado], PrincipalAutenticado]:
    """Crea un guard que exige al menos uno de los roles indicados (403 si no)."""

    if not roles_permitidos:
        raise ValueError("Debe indicarse al menos un rol permitido")
    permitidos = frozenset(roles_permitidos)

    def dependencia(
        principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    ) -> PrincipalAutenticado:
        if not permitidos & principal.roles:
            raise error_sin_permiso()
        return principal

    return dependencia


def obtener_unidad_de_trabajo(db: Session = Depends(get_db)) -> UnidadDeTrabajo:
    """Unidad de trabajo de la petición, sobre la sesión que abre y cierra get_db."""
    return UnidadDeTrabajo(db)
