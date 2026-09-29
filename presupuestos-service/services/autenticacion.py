"""Operaciones de aplicación para registro público y autenticación."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from services.ms1_auth.security.passwords import hash_contrasena, verificar_contrasena
from shared.auth import NombreRol


class CorreoRegistradoError(Exception):
    """El correo ya pertenece a una cuenta."""


class CredencialesInvalidasError(Exception):
    """El correo, la contraseña o el estado de la cuenta no permiten ingresar."""


class ConfiguracionRolesError(Exception):
    """Los roles oficiales todavía no están disponibles en la base de MS1."""


class PersistenciaAutenticacionError(Exception):
    """La operación no pudo persistirse o consultarse de manera segura."""


def registrar_cliente(
    db: Session,
    *,
    correo: str,
    contrasena: str,
    nombre: str,
) -> Usuario:
    """Crea una cuenta pública y le asigna exclusivamente el rol Cliente."""

    correo_normalizado = correo.strip().lower()
    try:
        if db.scalar(select(Usuario.usuario_id).where(Usuario.correo == correo_normalizado)):
            raise CorreoRegistradoError("El correo ya está registrado")

        rol_cliente = db.scalar(
            select(Rol).where(Rol.nombre == NombreRol.CLIENTE.value)
        )
        if rol_cliente is None:
            raise ConfiguracionRolesError("El rol cliente no está configurado")

        usuario = Usuario(
            correo=correo_normalizado,
            nombre=nombre,
            contrasena_hash=hash_contrasena(contrasena),
            activo=True,
        )
        usuario.roles.append(UsuarioRol(rol=rol_cliente))
        db.add(usuario)
        db.commit()
        return usuario
    except (CorreoRegistradoError, ConfiguracionRolesError, ValueError):
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise CorreoRegistradoError("El correo ya está registrado") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaAutenticacionError(
            "No fue posible registrar el usuario"
        ) from exc


def autenticar_usuario(db: Session, *, correo: str, contrasena: str) -> Usuario:
    """Valida credenciales sin revelar si el correo existe."""

    try:
        usuario = db.scalar(
            _consulta_usuario_completo().where(
                Usuario.correo == correo.strip().lower()
            )
        )
    except SQLAlchemyError as exc:
        raise PersistenciaAutenticacionError(
            "No fue posible consultar el usuario"
        ) from exc

    if (
        usuario is None
        or not usuario.activo
        or not verificar_contrasena(contrasena, usuario.contrasena_hash)
    ):
        raise CredencialesInvalidasError("Correo o contraseña incorrectos")
    return usuario


def buscar_usuario_activo_por_id(db: Session, usuario_id: int) -> Usuario | None:
    """Consulta el usuario actual de MS1 para el endpoint /auth/me."""

    try:
        return db.scalar(
            _consulta_usuario_completo().where(
                Usuario.usuario_id == usuario_id,
                Usuario.activo.is_(True),
            )
        )
    except SQLAlchemyError as exc:
        raise PersistenciaAutenticacionError(
            "No fue posible consultar el usuario"
        ) from exc


def roles_del_usuario(usuario: Usuario) -> frozenset[NombreRol]:
    """Obtiene y valida todos los roles ORM asociados a una cuenta."""

    try:
        roles = frozenset(NombreRol(asignacion.rol.nombre) for asignacion in usuario.roles)
    except ValueError as exc:
        raise ConfiguracionRolesError("El usuario posee un rol desconocido") from exc
    if not roles:
        raise ConfiguracionRolesError("El usuario no posee roles")
    return roles


def _consulta_usuario_completo():
    return (
        select(Usuario)
        .options(selectinload(Usuario.roles).selectinload(UsuarioRol.rol))
        .execution_options(populate_existing=True)
    )
