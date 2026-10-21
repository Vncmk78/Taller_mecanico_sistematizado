"""Operaciones de aplicación para registro público y autenticación."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import ceil

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from services.ms1_auth.config import settings
from services.ms1_auth.models.historial_rol import HistorialRol
from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from services.ms1_auth.security.passwords import hash_contrasena, verificar_contrasena
from shared.auth import NombreRol


class CorreoRegistradoError(Exception):
    """El correo ya pertenece a una cuenta."""


class UsuarioNoEncontradoError(Exception):
    """El usuario objetivo no existe en MS1."""


class CredencialesInvalidasError(Exception):
    """El correo, la contraseña o el estado de la cuenta no permiten ingresar."""


class CuentaBloqueadaError(Exception):
    """La cuenta está bloqueada temporalmente por intentos fallidos repetidos.

    Lleva los segundos que faltan para que el bloqueo expire, de modo que el
    router pueda anunciarlos en la cabecera `Retry-After`.
    """

    def __init__(self, segundos_restantes: int) -> None:
        super().__init__(
            "Demasiados intentos fallidos. Inténtalo de nuevo más tarde"
        )
        self.segundos_restantes = segundos_restantes


class ConfiguracionRolesError(Exception):
    """Los roles oficiales todavía no están disponibles en la base de MS1."""


class UsuarioSinRolesError(Exception):
    """La cuenta es correcta, pero no tiene ningún rol asignado."""


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
        # El alta inicial de `cliente` la hace el sistema: se registra en el
        # historial sin responsable, pero con su fecha y hora.
        db.flush()
        _registrar_cambio_de_rol(
            db,
            usuario_id=usuario.usuario_id,
            rol_id=rol_cliente.rol_id,
            accion="asignado",
            responsable_id=None,
        )
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
    """Valida credenciales sin revelar si el correo existe.

    Si la cuenta acumula `LOGIN_MAX_INTENTOS` fallos consecutivos queda
    bloqueada `LOGIN_BLOQUEO_MINUTOS` minutos: mientras el bloqueo siga
    vigente no se verifica la contraseña y se lanza `CuentaBloqueadaError`.
    Un ingreso correcto reinicia el contador y el bloqueo.
    """

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

    if usuario is not None:
        segundos_restantes = _segundos_bloqueo_restantes(usuario)
        if segundos_restantes > 0:
            raise CuentaBloqueadaError(segundos_restantes)

    if (
        usuario is None
        or not usuario.activo
        or not verificar_contrasena(contrasena, usuario.contrasena_hash)
    ):
        _registrar_intento_fallido(db, usuario)
        raise CredencialesInvalidasError("Correo o contraseña incorrectos")

    _reiniciar_intentos(db, usuario)
    return usuario


def _ahora() -> datetime:
    """Instante actual en UTC, consciente de zona horaria."""

    return datetime.now(timezone.utc)


def _como_utc(momento: datetime) -> datetime:
    """Normaliza a UTC un `datetime` que puede llegar sin zona (SQLite)."""

    if momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


def _segundos_bloqueo_restantes(usuario: Usuario) -> int:
    """Segundos que faltan para que expire el bloqueo; 0 si no hay o ya venció."""

    if usuario.bloqueado_hasta is None:
        return 0
    restante = _como_utc(usuario.bloqueado_hasta) - _ahora()
    if restante.total_seconds() <= 0:
        return 0
    return max(1, ceil(restante.total_seconds()))


def _registrar_intento_fallido(db: Session, usuario: Usuario | None) -> None:
    """Suma un fallo a la cuenta y la bloquea al superar el umbral.

    Se persiste de inmediato: el router responde 401 y la sesión se cierra, así
    que el contador debe quedar guardado antes de propagar el error. Cuando un
    bloqueo anterior ya venció, el contador arranca de nuevo para que el usuario
    vuelva a disponer de todos sus intentos.
    """

    if usuario is None:
        # El correo no existe: no hay cuenta a la que contar el fallo.
        return

    if usuario.bloqueado_hasta is not None and _segundos_bloqueo_restantes(usuario) == 0:
        usuario.bloqueado_hasta = None
        usuario.intentos_fallidos = 0

    usuario.intentos_fallidos += 1
    if usuario.intentos_fallidos >= settings.LOGIN_MAX_INTENTOS:
        usuario.bloqueado_hasta = _ahora() + timedelta(
            minutes=settings.LOGIN_BLOQUEO_MINUTOS
        )

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaAutenticacionError(
            "No fue posible registrar el intento fallido"
        ) from exc


def _reiniciar_intentos(db: Session, usuario: Usuario) -> None:
    """Limpia el contador y el bloqueo tras un ingreso correcto."""

    if usuario.intentos_fallidos == 0 and usuario.bloqueado_hasta is None:
        return

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaAutenticacionError(
            "No fue posible reiniciar los intentos fallidos"
        ) from exc


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


def listar_usuarios(db: Session) -> list[Usuario]:
    """Consulta todas las cuentas de MS1, activas y desactivadas.

    A diferencia de `buscar_usuario_activo_por_id` no filtra por `activo`: el
    administrador necesita ver también las cuentas desactivadas. Los roles
    vienen ya cargados, así que serializar la lista no dispara una consulta
    adicional por cada usuario.
    """

    try:
        return list(
            db.scalars(_consulta_usuario_completo().order_by(Usuario.usuario_id))
        )
    except SQLAlchemyError as exc:
        raise PersistenciaAutenticacionError(
            "No fue posible consultar los usuarios"
        ) from exc


def buscar_usuario_por_id(db: Session, *, usuario_id: int) -> Usuario:
    """Consulta una cuenta concreta por su identificador, activa o no."""

    try:
        usuario = db.scalar(
            _consulta_usuario_completo().where(Usuario.usuario_id == usuario_id)
        )
    except SQLAlchemyError as exc:
        raise PersistenciaAutenticacionError(
            "No fue posible consultar el usuario"
        ) from exc

    if usuario is None:
        raise UsuarioNoEncontradoError("El usuario no existe")
    return usuario


def asignar_rol_restringido(
    db: Session,
    *,
    usuario_id: int,
    rol: NombreRol,
    administrador_id: int,
) -> Usuario:
    """Agrega un rol restringido a una cuenta existente. Idempotente.

    Repetir el mismo rol no duplica la asignación: la clave primaria compuesta
    (usuario_id, rol_id) lo impide y aquí se devuelve el estado sin error.
    """

    try:
        usuario = db.scalar(
            _consulta_usuario_completo().where(Usuario.usuario_id == usuario_id)
        )
        if usuario is None:
            raise UsuarioNoEncontradoError("El usuario no existe")

        registro_rol = db.scalar(select(Rol).where(Rol.nombre == rol.value))
        if registro_rol is None:
            raise ConfiguracionRolesError("El rol no está configurado")

        ya_asignado = any(
            asignacion.rol_id == registro_rol.rol_id for asignacion in usuario.roles
        )
        if not ya_asignado:
            usuario.roles.append(
                UsuarioRol(rol=registro_rol, asignado_por_id=administrador_id)
            )
            _registrar_cambio_de_rol(
                db,
                usuario_id=usuario_id,
                rol_id=registro_rol.rol_id,
                accion="asignado",
                responsable_id=administrador_id,
            )
            db.commit()
        return _recargar_usuario(db, usuario_id)
    except (UsuarioNoEncontradoError, ConfiguracionRolesError):
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaAutenticacionError("No fue posible asignar el rol") from exc


def retirar_rol_restringido(
    db: Session,
    *,
    usuario_id: int,
    rol: NombreRol,
    administrador_id: int,
) -> Usuario:
    """Quita un rol restringido a una cuenta existente. Idempotente."""

    try:
        usuario = db.scalar(
            _consulta_usuario_completo().where(Usuario.usuario_id == usuario_id)
        )
        if usuario is None:
            raise UsuarioNoEncontradoError("El usuario no existe")

        asignacion = next(
            (
                item
                for item in usuario.roles
                if item.rol is not None and item.rol.nombre == rol.value
            ),
            None,
        )
        if asignacion is not None:
            rol_id = asignacion.rol_id
            usuario.roles.remove(asignacion)
            _registrar_cambio_de_rol(
                db,
                usuario_id=usuario_id,
                rol_id=rol_id,
                accion="retirado",
                responsable_id=administrador_id,
            )
            db.commit()
        return _recargar_usuario(db, usuario_id)
    except UsuarioNoEncontradoError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaAutenticacionError("No fue posible retirar el rol") from exc


def roles_del_usuario(usuario: Usuario) -> frozenset[NombreRol]:
    """Obtiene y valida todos los roles ORM asociados a una cuenta.

    Un rol desconocido sigue siendo error de configuración; una cuenta sin
    asignaciones lanza `UsuarioSinRolesError`, que es un estado legítimo que
    produce la propia retirada de roles.
    """

    try:
        roles = frozenset(NombreRol(asignacion.rol.nombre) for asignacion in usuario.roles)
    except ValueError as exc:
        raise ConfiguracionRolesError("El usuario posee un rol desconocido") from exc
    if not roles:
        raise UsuarioSinRolesError("El usuario no posee roles")
    return roles


def _registrar_cambio_de_rol(
    db: Session,
    *,
    usuario_id: int,
    rol_id: int,
    accion: str,
    responsable_id: int | None,
) -> None:
    """Añade una fila al historial de roles.

    No confirma: la fila se persiste junto con el cambio de `usuario_rol` en la
    misma transacción, de modo que historia y estado vigente nunca divergen.
    """

    db.add(
        HistorialRol(
            usuario_id=usuario_id,
            rol_id=rol_id,
            accion=accion,
            responsable_id=responsable_id,
        )
    )


def _recargar_usuario(db: Session, usuario_id: int) -> Usuario:
    """Relee la cuenta con sus roles ya cargados tras confirmar la escritura."""

    usuario = db.scalar(
        _consulta_usuario_completo().where(Usuario.usuario_id == usuario_id)
    )
    if usuario is None:  # pragma: no cover - la cuenta existe tras el commit
        raise UsuarioNoEncontradoError("El usuario no existe")
    return usuario


def _consulta_usuario_completo():
    return (
        select(Usuario)
        .options(selectinload(Usuario.roles).selectinload(UsuarioRol.rol))
        .execution_options(populate_existing=True)
    )
