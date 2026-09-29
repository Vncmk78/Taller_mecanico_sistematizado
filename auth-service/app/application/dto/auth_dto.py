"""DTOs de la capa de aplicación (independientes de FastAPI)."""
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.user import UserRole


@dataclass
class RegisterUserInput:
    email: str
    password: str
    full_name: str
    role: UserRole


@dataclass
class UserOutput:
    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool


@dataclass
class LoginOutput:
    access_token: str
    token_type: str
    user: UserOutput
