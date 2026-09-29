"""Implementación de TokenProvider usando JWT (python-jose). RF-02, RNF-07."""
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt

from app.domain.ports.token_provider import TokenProvider
from app.infrastructure.config import settings


class InvalidTokenError(Exception):
    """Se lanza cuando el token es inválido, está mal formado o expiró."""


class JWTTokenProvider(TokenProvider):
    def create_access_token(self, user_id: UUID, role: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
        payload = {
            "sub": str(user_id),
            "role": role,
            "exp": expire,
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        except JWTError as exc:
            raise InvalidTokenError("Token inválido o expirado") from exc
