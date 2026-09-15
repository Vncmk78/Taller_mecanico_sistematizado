"""Wiring de dependencias: conecta los puertos del dominio con sus implementaciones concretas."""
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.dto.auth_dto import UserOutput
from app.domain.entities.user import UserRole
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.token_provider import TokenProvider
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.db.session import get_db
from app.infrastructure.db.user_repository_sqlalchemy import SQLAlchemyUserRepository
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher
from app.infrastructure.security.jwt_provider import InvalidTokenError, JWTTokenProvider

_bearer_scheme = HTTPBearer()


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return SQLAlchemyUserRepository(db)


def get_password_hasher() -> PasswordHasher:
    return BcryptPasswordHasher()


def get_token_provider() -> TokenProvider:
    return JWTTokenProvider()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    user_repository: UserRepository = Depends(get_user_repository),
    token_provider: TokenProvider = Depends(get_token_provider),
) -> UserOutput:
    """RF-05: valida el JWT recibido en el header Authorization: Bearer <token>."""
    try:
        payload = token_provider.decode_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc

    user = user_repository.get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no válido")

    return UserOutput(
        id=user.id, email=user.email, full_name=user.full_name, role=user.role, is_active=user.is_active
    )


def require_role(*allowed_roles: UserRole):
    """RF-03: helper para proteger endpoints según el rol del usuario autenticado."""

    def dependency(current_user: UserOutput = Depends(get_current_user)) -> UserOutput:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para esto")
        return current_user

    return dependency
