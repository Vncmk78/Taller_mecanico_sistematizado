"""Puerto (interfaz) para la generación y validación de tokens JWT. RF-02, RNF-07."""
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class TokenProvider(ABC):
    @abstractmethod
    def create_access_token(self, user_id: UUID, role: str) -> str:
        """Crea un JWT firmado que contiene el id del usuario y su rol."""

    @abstractmethod
    def decode_token(self, token: str) -> dict[str, Any]:
        """Decodifica y valida un JWT. Lanza excepción si es inválido o expiró."""
