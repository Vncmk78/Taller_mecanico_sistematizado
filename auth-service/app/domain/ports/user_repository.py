"""Puerto (interfaz) de persistencia de usuarios. La infraestructura la implementa."""
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from app.domain.entities.user import User


class UserRepository(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]: ...

    @abstractmethod
    def get_by_id(self, user_id: UUID) -> Optional[User]: ...

    @abstractmethod
    def save(self, user: User) -> User: ...

    @abstractmethod
    def email_exists(self, email: str) -> bool: ...
