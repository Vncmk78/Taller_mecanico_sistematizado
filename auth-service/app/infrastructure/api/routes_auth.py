"""Endpoints HTTP de autenticación. RF-01 a RF-05."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.dto.auth_dto import RegisterUserInput
from app.application.use_cases.login_user import InvalidCredentialsError, LoginUserUseCase
from app.application.use_cases.register_user import EmailAlreadyRegisteredError, RegisterUserUseCase
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.token_provider import TokenProvider
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.api.dependencies import (
    get_current_user,
    get_password_hasher,
    get_token_provider,
    get_user_repository,
)
from app.infrastructure.api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.application.dto.auth_dto import UserOutput

router = APIRouter(prefix="/auth", tags=["Autenticación y Usuarios"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    user_repository: UserRepository = Depends(get_user_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
):
    use_case = RegisterUserUseCase(user_repository, password_hasher)
    try:
        return use_case.execute(
            RegisterUserInput(
                email=body.email, password=body.password, full_name=body.full_name, role=body.role
            )
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    user_repository: UserRepository = Depends(get_user_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
    token_provider: TokenProvider = Depends(get_token_provider),
):
    use_case = LoginUserUseCase(user_repository, password_hasher, token_provider)
    try:
        return use_case.execute(body.email, body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get("/me", response_model=UserResponse)
def me(current_user: UserOutput = Depends(get_current_user)):
    """RF-05: usado por el frontend/gateway para validar la sesión con el token guardado."""
    return current_user
