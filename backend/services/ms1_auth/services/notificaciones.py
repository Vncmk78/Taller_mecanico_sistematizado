"""Creación idempotente y consulta de notificaciones en MS1."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from services.ms1_auth.models.notificacion import Notificacion
from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from services.ms1_auth.schemas.notificacion import EventoEstadoOrden


class DestinatarioNotificacionInvalidoError(Exception):
    """El identificador no corresponde a un cliente activo de MS1."""


class PersistenciaNotificacionError(Exception):
    """No fue posible persistir o consultar el aviso."""


def recibir_evento_estado_orden(
    db: Session, evento: EventoEstadoOrden
) -> tuple[Notificacion, bool]:
    """Persiste un aviso una vez; reintentos con el mismo evento son inocuos."""
    try:
        existente = db.scalar(
            select(Notificacion).where(Notificacion.evento_id == evento.evento_id)
        )
        if existente is not None:
            return existente, True

        destinatario = db.scalar(
            select(Usuario)
            .join(UsuarioRol, UsuarioRol.usuario_id == Usuario.usuario_id)
            .join(Rol, Rol.rol_id == UsuarioRol.rol_id)
            .where(
                Usuario.usuario_id == evento.cliente_usuario_id,
                Usuario.activo.is_(True),
                Rol.nombre == "cliente",
            )
        )
        if destinatario is None:
            raise DestinatarioNotificacionInvalidoError

        notificacion = Notificacion(
            evento_id=evento.evento_id,
            destinatario_id=destinatario.usuario_id,
            tipo=evento.tipo,
            orden_id=evento.orden_id,
            vehiculo_id=evento.vehiculo_id,
            titulo="Actualización de tu orden",
            mensaje="El estado de tu orden de trabajo cambió. Consulta el detalle para ver su estado actual.",
            ocurrido_en=evento.ocurrido_en,
        )
        db.add(notificacion)
        db.commit()
        db.refresh(notificacion)
        return notificacion, False
    except DestinatarioNotificacionInvalidoError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        # Dos entregas concurrentes del mismo evento pueden competir por la
        # clave única. Si la otra transacción ganó, devolvemos su aviso.
        existente = db.scalar(
            select(Notificacion).where(Notificacion.evento_id == evento.evento_id)
        )
        if existente is not None:
            return existente, True
        raise PersistenciaNotificacionError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaNotificacionError from exc


def listar_notificaciones(
    db: Session, *, destinatario_id: int, limite: int, offset: int
) -> list[Notificacion]:
    try:
        return list(
            db.scalars(
                select(Notificacion)
                .where(Notificacion.destinatario_id == destinatario_id)
                .order_by(Notificacion.creado_en.desc(), Notificacion.notificacion_id.desc())
                .limit(limite)
                .offset(offset)
            )
        )
    except SQLAlchemyError as exc:
        raise PersistenciaNotificacionError from exc
