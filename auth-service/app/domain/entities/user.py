"""Entidad de dominio User. No depende de FastAPI, SQLAlchemy ni ningún framework."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class UserRole(str, Enum):
    CLIENTE = "cliente"
    MECANICO = "mecanico"
    ADMINISTRADOR = "administrador"


@dataclass
class User:
    email: str
    hashed_password: str
    full_name: str
    role: UserRole
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
