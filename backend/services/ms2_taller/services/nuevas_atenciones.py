"""Alta y consulta de solicitudes; no crea órdenes, ingresos ni notificaciones."""
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from services.ms2_taller.models.cliente import Cliente
from services.ms2_taller.models.estado_orden import CANCELADO
from services.ms2_taller.models.orden_trabajo import OrdenTrabajo
from services.ms2_taller.models.solicitud_nueva_atencion import SolicitudNuevaAtencion
from services.ms2_taller.models.vehiculo import Vehiculo
from shared.auth import NombreRol, PrincipalAutenticado


class NuevaAtencionNoAutorizadaError(Exception):
    """La identidad no tiene un rol permitido para esta operación."""


class NuevaAtencionNoEncontradaError(Exception):
    """El antecedente o la solicitud no existen o no son visibles."""


class NuevaAtencionConflictoError(Exception):
    """El antecedente o una solicitud vigente impiden una nueva solicitud."""


class NuevaAtencionInvalidaError(Exception):
    """La descripción no cumple las reglas del servicio."""


class PersistenciaNuevaAtencionError(Exception):
    """La operación no pudo completarse contra la base propia de MS2."""


def solicitar_nueva_atencion(
    db: Session, *, orden_id: int, principal: PrincipalAutenticado, descripcion: str,
) -> tuple[SolicitudNuevaAtencion, bool]:
    if NombreRol.CLIENTE not in principal.roles:
        raise NuevaAtencionNoAutorizadaError("Se requiere rol Cliente")
    descripcion = descripcion.strip()
    if not descripcion or len(descripcion) > 2000:
        raise NuevaAtencionInvalidaError("La descripción debe tener entre 1 y 2000 caracteres")
    try:
        # La salida/alta bloquean vehículo antes que orden. Mantener ese orden
        # evita un ciclo entre el lock de la orden y la FK al vehículo al insertar.
        vehiculo_id = db.scalar(
            select(Vehiculo.vehiculo_id)
            .join(OrdenTrabajo, OrdenTrabajo.vehiculo_id == Vehiculo.vehiculo_id)
            .join(Cliente, Cliente.cliente_id == Vehiculo.cliente_id)
            .where(OrdenTrabajo.orden_id == orden_id, Cliente.usuario_id == principal.usuario_id)
            .with_for_update(of=Vehiculo)
        )
        if vehiculo_id is None:
            raise NuevaAtencionNoEncontradaError("Orden no encontrada")
        # El padre siempre existe: su lock serializa incluso el primer INSERT;
        # no hay un hueco entre «no existe solicitud» y crearla en PostgreSQL.
        orden = db.scalar(
            select(OrdenTrabajo)
            .join(Vehiculo, Vehiculo.vehiculo_id == OrdenTrabajo.vehiculo_id)
            .join(Cliente, Cliente.cliente_id == Vehiculo.cliente_id)
            .where(OrdenTrabajo.orden_id == orden_id, Cliente.usuario_id == principal.usuario_id)
            .with_for_update(of=OrdenTrabajo)
            .execution_options(populate_existing=True)
        )
        if orden is None:
            raise NuevaAtencionNoEncontradaError("Orden no encontrada")
        if orden.estado_codigo != CANCELADO:
            raise NuevaAtencionConflictoError("La nueva atención solo se solicita sobre una orden Cancelada")
        existente = db.scalar(select(SolicitudNuevaAtencion).where(
            SolicitudNuevaAtencion.orden_cancelada_id == orden_id,
            SolicitudNuevaAtencion.situacion != "rechazada",
        ).with_for_update().execution_options(populate_existing=True))
        if existente is not None:
            if existente.situacion == "pendiente" and existente.descripcion == descripcion:
                db.commit()
                return existente, False
            raise NuevaAtencionConflictoError("La orden ya tiene una solicitud de nueva atención pendiente o aceptada")
        solicitud = SolicitudNuevaAtencion(
            orden_cancelada_id=orden.orden_id, vehiculo_id=orden.vehiculo_id,
            cliente_usuario_id=principal.usuario_id, descripcion=descripcion,
        )
        db.add(solicitud)
        db.flush()
        db.refresh(solicitud)
        db.commit()
        return solicitud, True
    except (NuevaAtencionNoEncontradaError, NuevaAtencionConflictoError):
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaNuevaAtencionError("No fue posible registrar la solicitud de nueva atención") from exc


def _consulta_visible(principal: PrincipalAutenticado):
    consulta = select(SolicitudNuevaAtencion)
    if NombreRol.ADMINISTRADOR in principal.roles:
        return consulta
    if NombreRol.CLIENTE in principal.roles:
        return consulta.where(SolicitudNuevaAtencion.cliente_usuario_id == principal.usuario_id)
    raise NuevaAtencionNoAutorizadaError("Se requiere rol Cliente o Administrador")


def listar_nuevas_atenciones(
    db: Session, *, principal: PrincipalAutenticado, situacion: str | None = None,
    orden_cancelada_id: int | None = None, orden_generada_id: int | None = None,
    limit: int = 20, offset: int = 0,
) -> tuple[list[SolicitudNuevaAtencion], int]:
    consulta = _consulta_visible(principal)
    for campo, valor in ((SolicitudNuevaAtencion.situacion, situacion),
                         (SolicitudNuevaAtencion.orden_cancelada_id, orden_cancelada_id),
                         (SolicitudNuevaAtencion.orden_generada_id, orden_generada_id)):
        if valor is not None:
            consulta = consulta.where(campo == valor)
    try:
        total = db.scalar(select(func.count()).select_from(consulta.subquery()))
        items = list(db.scalars(consulta.order_by(
            SolicitudNuevaAtencion.solicitada_en.desc(), SolicitudNuevaAtencion.solicitud_id.desc(),
        ).limit(limit).offset(offset)))
        return items, total
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaNuevaAtencionError("No fue posible consultar las solicitudes de nueva atención") from exc


def obtener_nueva_atencion(
    db: Session, *, solicitud_id: int, principal: PrincipalAutenticado,
) -> SolicitudNuevaAtencion:
    consulta = _consulta_visible(principal).where(SolicitudNuevaAtencion.solicitud_id == solicitud_id)
    try:
        solicitud = db.scalar(consulta)
        if solicitud is None:
            raise NuevaAtencionNoEncontradaError("Solicitud de nueva atención no encontrada")
        return solicitud
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaNuevaAtencionError("No fue posible consultar la solicitud de nueva atención") from exc
