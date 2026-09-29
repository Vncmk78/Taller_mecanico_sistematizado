"""Contrato común y puro de autenticación para los microservicios.

Este módulo no importa FastAPI, SQLAlchemy ni modelos de MS1. Su única
responsabilidad es emitir y validar JWT con el contrato compartido por la
Gateway y los microservicios.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from jose import JWTError, jwt


class NombreRol(str, Enum):
    """Roles oficiales definidos por la sistematización."""

    CLIENTE = "cliente"
    MECANICO = "mecanico"
    ADMINISTRADOR = "administrador"


@dataclass(frozen=True)
class PrincipalAutenticado:
    """Identidad confiable obtenida después de validar un JWT."""

    usuario_id: int
    roles: frozenset[NombreRol]


class TokenInvalidoError(ValueError):
    """El JWT no cumple el contrato de autenticación del sistema."""


class ConfiguracionJWTError(RuntimeError):
    """La configuración del firmante o validador JWT no es segura."""


def crear_token_acceso(
    usuario_id: int,
    roles: Collection[NombreRol | str],
    *,
    clave_secreta: str,
    algoritmo: str = "HS256",
    minutos_expiracion: int = 60,
) -> str:
    """Crea un JWT usando el contrato oficial de identidad y roles."""

    if usuario_id <= 0:
        raise ValueError("usuario_id debe ser un entero positivo")
    if minutos_expiracion <= 0:
        raise ValueError("minutos_expiracion debe ser positivo")
    _validar_configuracion(clave_secreta, algoritmo)

    roles_normalizados = _normalizar_roles(roles)
    expira_en = datetime.now(timezone.utc) + timedelta(minutes=minutos_expiracion)
    payload = {
        "sub": str(usuario_id),
        "roles": [rol.value for rol in sorted(roles_normalizados, key=lambda rol: rol.value)],
        "exp": expira_en,
    }
    return jwt.encode(payload, clave_secreta, algorithm=algoritmo)


def validar_token_acceso(
    token: str,
    *,
    clave_secreta: str,
    algoritmo: str = "HS256",
) -> PrincipalAutenticado:
    """Valida firma, expiración y claims obligatorios sin consultar una BD."""

    _validar_configuracion(clave_secreta, algoritmo)
    try:
        payload = jwt.decode(
            token,
            clave_secreta,
            algorithms=[algoritmo],
            options={"require_exp": True, "require_sub": True},
        )
    except JWTError as exc:
        raise TokenInvalidoError("Token inválido o expirado") from exc

    usuario_id = _extraer_usuario_id(payload.get("sub"))
    roles = _extraer_roles(payload.get("roles"))
    return PrincipalAutenticado(usuario_id=usuario_id, roles=roles)


def _validar_configuracion(clave_secreta: str, algoritmo: str) -> None:
    if not clave_secreta:
        raise ConfiguracionJWTError("JWT_SECRET_KEY no está configurada")
    if len(clave_secreta) < 32:
        raise ConfiguracionJWTError("JWT_SECRET_KEY debe tener al menos 32 caracteres")
    if algoritmo != "HS256":
        raise ConfiguracionJWTError("El contrato actual solo admite HS256")


def _extraer_usuario_id(valor: object) -> int:
    if not isinstance(valor, str) or not valor.isdecimal():
        raise TokenInvalidoError("El claim sub debe representar un entero positivo")
    usuario_id = int(valor)
    if usuario_id <= 0:
        raise TokenInvalidoError("El claim sub debe representar un entero positivo")
    return usuario_id


def _extraer_roles(valor: object) -> frozenset[NombreRol]:
    if not isinstance(valor, list) or not valor:
        raise TokenInvalidoError("El claim roles debe ser una lista no vacía")
    if any(not isinstance(nombre, str) for nombre in valor):
        raise TokenInvalidoError("El claim roles contiene un valor inválido")

    try:
        roles = frozenset(NombreRol(nombre) for nombre in valor)
    except ValueError as exc:
        raise TokenInvalidoError("El claim roles contiene un rol desconocido") from exc
    if len(roles) != len(valor):
        raise TokenInvalidoError("El claim roles contiene valores duplicados")
    return roles


def _normalizar_roles(
    roles: Collection[NombreRol | str],
) -> frozenset[NombreRol]:
    if isinstance(roles, (str, bytes)) or not roles:
        raise ValueError("roles debe ser una colección no vacía")
    try:
        normalizados = frozenset(
            rol if isinstance(rol, NombreRol) else NombreRol(rol) for rol in roles
        )
    except ValueError as exc:
        raise ValueError("roles contiene un rol desconocido") from exc
    if len(normalizados) != len(roles):
        raise ValueError("roles contiene valores duplicados")
    return normalizados
