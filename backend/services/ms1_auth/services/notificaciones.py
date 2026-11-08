"""Creación idempotente y consulta de notificaciones en MS1."""
from __future__ import annotations

from sqlalchemy import func, select, update
from uuid import uuid5
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from services.ms1_auth.models.notificacion import Notificacion
from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from services.ms1_auth.schemas.notificacion import EventoEstadoOrden, EventoRevisionNuevaAtencion, EventoSolicitudNuevaAtencion


class DestinatarioNotificacionInvalidoError(Exception):
    """El identificador no corresponde a un cliente activo de MS1."""


class PersistenciaNotificacionError(Exception):
    """No fue posible persistir o consultar el aviso."""


def recibir_evento_estado_orden(
    db: Session, evento: EventoEstadoOrden
) -> tuple[Notificacion, bool]:
    """Persiste un aviso una vez; reintentos con el mismo evento son inocuos."""
    return _recibir_aviso(db, evento, orden_id=evento.orden_id,
                         titulo="Actualización de tu orden",
                         mensaje="El estado de tu orden de trabajo cambió. Consulta el detalle para ver su estado actual.")


def recibir_evento_revision_nueva_atencion(
    db: Session, evento: EventoRevisionNuevaAtencion,
) -> tuple[Notificacion, bool]:
    return _recibir_aviso(
        db, evento, orden_id=evento.orden_cancelada_id,
        titulo=f"Solicitud de nueva atención {evento.decision}",
        mensaje=(f"El taller revisó la solicitud n° {evento.solicitud_id}: {evento.decision}. "
                 f"Consulta la respuesta en Nuevas Atenciones o desde la orden cancelada n° {evento.orden_cancelada_id}."),
    )


def _recibir_aviso(
    db: Session, evento: EventoEstadoOrden | EventoRevisionNuevaAtencion,
    *, orden_id: int, titulo: str, mensaje: str,
) -> tuple[Notificacion, bool]:
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
            orden_id=orden_id,
            vehiculo_id=evento.vehiculo_id,
            titulo=titulo,
            mensaje=mensaje,
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
    db: Session, *, destinatario_id: int, limite: int, offset: int, solo_no_leidas: bool = False
) -> list[Notificacion]:
    try:
        return list(
            db.scalars(
                select(Notificacion)
                .where(Notificacion.destinatario_id == destinatario_id,
                       *([Notificacion.leida.is_(False)] if solo_no_leidas else []))
                .order_by(Notificacion.creado_en.desc(), Notificacion.notificacion_id.desc())
                .limit(limite)
                .offset(offset)
            )
        )
    except SQLAlchemyError as exc:
        raise PersistenciaNotificacionError from exc


def marcar_leida(db: Session, *, destinatario_id: int, notificacion_id: int | None = None) -> bool:
    """Actualización propia e idempotente: conserva la fecha del primer marcado."""
    try:
        condiciones = [Notificacion.destinatario_id == destinatario_id]
        if notificacion_id is not None:
            condiciones.append(Notificacion.notificacion_id == notificacion_id)
            if db.scalar(select(Notificacion.notificacion_id).where(*condiciones)) is None:
                return False
        db.execute(update(Notificacion).where(*condiciones, Notificacion.leida.is_(False))
                   .values(leida=True, leida_en=func.now()))
        db.commit()
        return True
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaNotificacionError from exc


def contar_notificaciones(db: Session, *, destinatario_id: int) -> tuple[int, int]:
    try:
        total, no_leidas = db.execute(select(
            func.count(Notificacion.notificacion_id),
            func.count(Notificacion.notificacion_id).filter(Notificacion.leida.is_(False)),
        ).where(Notificacion.destinatario_id == destinatario_id)).one()
        return total, no_leidas
    except SQLAlchemyError as exc:
        raise PersistenciaNotificacionError from exc


def recibir_solicitud_nueva_atencion(db: Session, evento: EventoSolicitudNuevaAtencion) -> tuple[int, int]:
    """Un aviso por administrador activo; UUID derivado estable por destinatario.

    Las altas de personal no reenvían eventos históricos ya confirmados. Si una
    entrega necesita repetirse, cada destinatario sigue teniendo un solo aviso.
    Toda la distribución se confirma junta dentro de MS1.
    """
    try:
        destinatarios = list(db.scalars(select(Usuario.usuario_id).join(UsuarioRol, UsuarioRol.usuario_id == Usuario.usuario_id).join(Rol, Rol.rol_id == UsuarioRol.rol_id)
            .where(Usuario.activo.is_(True), Rol.nombre == "administrador").order_by(Usuario.usuario_id)))
        creadas = existentes = 0
        for uid in destinatarios:
            clave = uuid5(evento.evento_id, f"administrador:{uid}")
            if db.scalar(select(Notificacion.notificacion_id).where(Notificacion.evento_id == clave)) is not None:
                existentes += 1
                continue
            db.add(Notificacion(evento_id=clave, destinatario_id=uid, tipo=evento.tipo,
                orden_id=evento.orden_cancelada_id, vehiculo_id=evento.vehiculo_id,
                titulo="Solicitud de nueva atención pendiente",
                mensaje=f"El Cliente solicitó una nueva atención (solicitud n° {evento.solicitud_id}, orden cancelada n° {evento.orden_cancelada_id}). Revísela en Nuevas atenciones.",
                ocurrido_en=evento.ocurrido_en))
            creadas += 1
        db.commit()
        return creadas, existentes
    except IntegrityError as exc:
        db.rollback()
        # Un recibo concurrente puede adelantarse. El productor reintenta el
        # mismo UUID; no se confirma parcialmente ni se crean avisos nuevos.
        raise PersistenciaNotificacionError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaNotificacionError from exc
