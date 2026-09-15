"""Caso de uso: autenticar un usuario y emitir un JWT. RF-01, RF-02."""
from app.application.dto.auth_dto import LoginOutput, UserOutput
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.token_provider import TokenProvider
from app.domain.ports.user_repository import UserRepository


class InvalidCredentialsError(Exception):
    """Se lanza cuando el correo no existe, el usuario está inactivo o la clave no coincide."""


class LoginUserUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        token_provider: TokenProvider,
    ):
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._token_provider = token_provider

    def execute(self, email: str, password: str) -> LoginOutput:
        user = self._user_repository.get_by_email(email)

        # Mismo mensaje de error exista o no el correo: evita filtrar información (user enumeration).
        if user is None or not user.is_active:
            raise InvalidCredentialsError("Correo o contraseña incorrectos")

        if not self._password_hasher.verify(password, user.hashed_password):
            raise InvalidCredentialsError("Correo o contraseña incorrectos")

        token = self._token_provider.create_access_token(user.id, user.role.value)

        return LoginOutput(
            access_token=token,
            token_type="bearer",
            user=UserOutput(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=user.is_active,
            ),
        )
