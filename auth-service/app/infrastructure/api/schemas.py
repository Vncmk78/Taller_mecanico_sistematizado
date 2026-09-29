"""Esquemas Pydantic (request/response) de la API HTTP. No confundir con entidades de dominio."""
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.domain.entities.user import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Mínimo 8 caracteres")
    full_name: str = Field(min_length=2, max_length=255)
    role: UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
