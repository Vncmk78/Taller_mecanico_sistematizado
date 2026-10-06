"""Endpoints de registro, autenticación y usuario actual de MS1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.ms1_auth.config import settings
from services.ms1_auth.db import get_db
from services.ms1_auth.dependencies import obtener_usuario_actual, requerir_roles
from services.ms1_auth.models.usuario import Usuario
from services.ms1_auth.schemas.auth import (
    LoginSolicitud,
    RegistroClienteSolicitud,
    RolAsignarSolicitud,
    TokenRespuesta,
    UsuarioRespuesta,
)
from services.ms1_auth.services.autenticacion import (
    ConfiguracionRolesError,
    CorreoRegistradoError,
    CredencialesInvalidasError,
    PersistenciaAutenticacionError,
    UsuarioNoEncontradoError,
    asignar_rol_restringido,
    autenticar_usuario,
    registrar_cliente,
    retirar_rol_restringido,
    roles_del_usuario,
)
from shared.auth import NombreRol, PrincipalAutenticado, crear_token_acceso

router_auth = APIRouter(prefix="/auth", tags=["autenticación y usuarios"])


@router_auth.post(
    "/register",
    response_model=UsuarioRespuesta,
    status_code=status.HTTP_201_CREATED,
)
def registrar(
    body: RegistroClienteSolicitud,
    db: Session = Depends(get_db),
) -> UsuarioRespuesta:
    try:
        usuario = registrar_cliente(
            db,
            correo=str(body.email),
            contrasena=body.password,
            nombre=body.full_name,
        )
        return _serializar_usuario(usuario)
    except CorreoRegistradoError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ConfiguracionRolesError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except PersistenciaAutenticacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar el usuario",
        ) from exc


@router_auth.post("/login", response_model=TokenRespuesta)
def login(
    body: LoginSolicitud,
    db: Session = Depends(get_db),
) -> TokenRespuesta:
    try:
        usuario = autenticar_usuario(
            db,
            correo=str(body.email),
            contrasena=body.password,
        )
        roles = roles_del_usuario(usuario)
        token = crear_token_acceso(
            usuario.usuario_id,
            roles,
            clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
            algoritmo=settings.JWT_ALGORITHM,
            minutos_expiracion=settings.JWT_EXPIRE_MINUTES,
        )
        return TokenRespuesta(
            access_token=token,
            user=_serializar_usuario(usuario),
        )
    except CredencialesInvalidasError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ConfiguracionRolesError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except PersistenciaAutenticacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible autenticar el usuario",
        ) from exc


@router_auth.get("/me", response_model=UsuarioRespuesta)
def consultar_usuario_actual(
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> UsuarioRespuesta:
    return _serializar_usuario(usuario)


@router_auth.post(
    "/usuarios/{usuario_id}/roles",
    response_model=UsuarioRespuesta,
    summary="Asignar un rol restringido a un usuario",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_404_NOT_FOUND: {"description": "El usuario no existe"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
    },
)
def asignar_rol_a_usuario(
    usuario_id: int,
    body: RolAsignarSolicitud,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(
        requerir_roles(NombreRol.ADMINISTRADOR)
    ),
) -> UsuarioRespuesta:
    try:
        usuario = asignar_rol_restringido(
            db,
            usuario_id=usuario_id,
            rol=body.rol,
            administrador_id=principal.usuario_id,
        )
        return _serializar_usuario(usuario)
    except UsuarioNoEncontradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (ConfiguracionRolesError, PersistenciaAutenticacionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible asignar el rol",
        ) from exc


@router_auth.delete(
    "/usuarios/{usuario_id}/roles/{rol}",
    response_model=UsuarioRespuesta,
    summary="Retirar un rol restringido a un usuario",
    dependencies=[Depends(requerir_roles(NombreRol.ADMINISTRADOR))],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_404_NOT_FOUND: {"description": "El usuario no existe"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
    },
)
def retirar_rol_de_usuario(
    usuario_id: int,
    rol: NombreRol,
    db: Session = Depends(get_db),
) -> UsuarioRespuesta:
    try:
        usuario = retirar_rol_restringido(
            db, usuario_id=usuario_id, rol=rol
        )
        return _serializar_usuario(usuario)
    except UsuarioNoEncontradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (ConfiguracionRolesError, PersistenciaAutenticacionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible retirar el rol",
        ) from exc


def _serializar_usuario(usuario: Usuario) -> UsuarioRespuesta:
    roles = sorted(roles_del_usuario(usuario), key=lambda rol: rol.value)
    return UsuarioRespuesta(
        id=usuario.usuario_id,
        email=usuario.correo,
        full_name=usuario.nombre,
        roles=roles,
        is_active=usuario.activo,
    )
