"""Puerto (interfaz) para el hashing de contraseñas. RNF-06."""
from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, plain_password: str) -> str:
        """Genera un hash seguro (nunca reversible) de la contraseña en texto plano."""

    @abstractmethod
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Verifica si la contraseña en texto plano corresponde al hash almacenado."""
