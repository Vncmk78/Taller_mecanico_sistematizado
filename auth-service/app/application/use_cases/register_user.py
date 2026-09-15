"""Caso de uso: registrar un nuevo usuario (cliente, mecánico o administrador)."""
from app.application.dto.auth_dto import RegisterUserInput, UserOutput
from app.domain.entities.user import User
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.user_repository import UserRepository


class EmailAlreadyRegisteredError(Exception):
    """Se lanza cuando el correo ya existe en el sistema."""


class RegisterUserUseCase:
    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher):
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    def execute(self, data: RegisterUserInput) -> UserOutput:
        if self._user_repository.email_exists(data.email):
            raise EmailAlreadyRegisteredError(f"El correo {data.email} ya está registrado")

        # RNF-06: la contraseña nunca se guarda en texto plano.
        hashed_password = self._password_hasher.hash(data.password)

        user = User(
            email=data.email,
            hashed_password=hashed_password,
            full_name=data.full_name,
            role=data.role,
        )
        saved_user = self._user_repository.save(user)

        return UserOutput(
            id=saved_user.id,
            email=saved_user.email,
            full_name=saved_user.full_name,
            role=saved_user.role,
            is_active=saved_user.is_active,
        )
