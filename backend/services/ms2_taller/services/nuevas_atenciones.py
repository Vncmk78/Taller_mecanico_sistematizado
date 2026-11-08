"""Solicitud, revisión y creación vinculada; transacciones locales de MS2."""
from datetime import timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from services.ms2_taller.models.cliente import Cliente
from services.ms2_taller.models.estado_orden import CANCELADO
from services.ms2_taller.models.orden_trabajo import OrdenTrabajo
from services.ms2_taller.models.solicitud_nueva_atencion import SolicitudNuevaAtencion
from services.ms2_taller.models.vehiculo import Vehiculo
from services.ms2_taller.models.evento_outbox import EventoOutbox
from services.ms2_taller.services.ordenes import (
    registrar_orden_sin_confirmar, VehiculoConOrdenActivaError, VehiculoNoEncontradoError,
)
from services.ms2_taller.services.cupo_ingresos import (
    CupoDiarioNoConfiguradoError, CupoDiarioExcedidoError,
    PersistenciaCupoIngresosError, registrar_rechazo_cupo,
)
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


def _exigir_administrador(principal: PrincipalAutenticado) -> None:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise NuevaAtencionNoAutorizadaError("Se requiere rol Administrador")


def _bloquear_solicitud_y_antecedente(db: Session, solicitud_id: int):
    referencias = db.execute(select(
        SolicitudNuevaAtencion.vehiculo_id, SolicitudNuevaAtencion.orden_cancelada_id,
    ).where(SolicitudNuevaAtencion.solicitud_id == solicitud_id)).one_or_none()
    if referencias is None:
        raise NuevaAtencionNoEncontradaError("Solicitud de nueva atención no encontrada")
    # Mismo protocolo que alta, solicitud y salida: vehículo → orden → solicitud.
    db.scalar(select(Vehiculo.vehiculo_id).where(
        Vehiculo.vehiculo_id == referencias.vehiculo_id,
    ).with_for_update())
    antecedente = db.scalar(select(OrdenTrabajo).where(
        OrdenTrabajo.orden_id == referencias.orden_cancelada_id,
    ).with_for_update(of=OrdenTrabajo).execution_options(populate_existing=True))
    solicitud = db.scalar(select(SolicitudNuevaAtencion).where(
        SolicitudNuevaAtencion.solicitud_id == solicitud_id,
    ).with_for_update().execution_options(populate_existing=True))
    if solicitud is None:
        raise NuevaAtencionNoEncontradaError("Solicitud de nueva atención no encontrada")
    if antecedente is None or antecedente.vehiculo_id != solicitud.vehiculo_id:
        raise NuevaAtencionConflictoError("El antecedente no corresponde al vehículo de la solicitud")
    return solicitud, antecedente


def revisar_nueva_atencion(
    db: Session, *, solicitud_id: int, principal: PrincipalAutenticado,
    decision: str, respuesta: str,
) -> SolicitudNuevaAtencion:
    _exigir_administrador(principal)
    respuesta = respuesta.strip()
    if decision not in {"aceptada", "rechazada"} or not respuesta:
        raise NuevaAtencionInvalidaError("La revisión requiere una decisión válida y una respuesta no vacía")
    try:
        solicitud, _ = _bloquear_solicitud_y_antecedente(db, solicitud_id)
        if solicitud.situacion != "pendiente":
            if solicitud.situacion == decision and solicitud.respuesta == respuesta:
                db.commit()
                return solicitud
            raise NuevaAtencionConflictoError("La solicitud ya tiene una revisión confirmada con otro contenido")
        fecha = db.scalar(select(func.now()))
        solicitud.situacion = decision
        solicitud.respuesta = respuesta
        solicitud.revisor_id = principal.usuario_id
        solicitud.revisada_en = fecha
        evento_id = uuid4()
        db.add(EventoOutbox(
            evento_id=evento_id, tipo="nueva_atencion.revisada",
            payload={
                "evento_id": str(evento_id), "tipo": "nueva_atencion.revisada",
                "ocurrido_en": (fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)).isoformat(),
                "solicitud_id": solicitud.solicitud_id,
                "orden_cancelada_id": solicitud.orden_cancelada_id,
                "vehiculo_id": solicitud.vehiculo_id, "cliente_usuario_id": solicitud.cliente_usuario_id,
                "decision": decision, "revisor_id": principal.usuario_id,
            },
        ))
        db.flush()
        db.refresh(solicitud)
        db.commit()
        return solicitud
    except (NuevaAtencionNoEncontradaError, NuevaAtencionConflictoError):
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaNuevaAtencionError("No fue posible registrar la revisión de nueva atención") from exc


def generar_orden_nueva_atencion(
    db: Session, *, solicitud_id: int, principal: PrincipalAutenticado,
) -> tuple[SolicitudNuevaAtencion, OrdenTrabajo, bool]:
    _exigir_administrador(principal)
    try:
        solicitud, antecedente = _bloquear_solicitud_y_antecedente(db, solicitud_id)
        if solicitud.orden_generada_id is not None:
            orden = db.get(OrdenTrabajo, solicitud.orden_generada_id, populate_existing=True)
            if orden is None or orden.vehiculo_id != solicitud.vehiculo_id:
                raise NuevaAtencionConflictoError("La asociación histórica de la solicitud requiere revisión")
            db.commit()
            return solicitud, orden, False
        if solicitud.situacion != "aceptada":
            raise NuevaAtencionConflictoError("La solicitud debe estar aceptada para generar una orden")
        if antecedente.estado_codigo != CANCELADO:
            raise NuevaAtencionConflictoError("La orden de referencia debe permanecer Cancelada")
        orden = registrar_orden_sin_confirmar(db, solicitud.vehiculo_id, principal.usuario_id)
        solicitud.orden_generada_id = orden.orden_id
        db.flush()
        db.commit()
        return solicitud, orden, True
    except (NuevaAtencionNoEncontradaError, NuevaAtencionConflictoError):
        db.rollback()
        raise
    except (VehiculoConOrdenActivaError, VehiculoNoEncontradoError) as exc:
        db.rollback()
        raise NuevaAtencionConflictoError(str(exc)) from exc
    except (CupoDiarioNoConfiguradoError, CupoDiarioExcedidoError) as exc:
        db.rollback()
        if exc.rechazo is not None:
            try:
                registrar_rechazo_cupo(db, exc.rechazo)
            except PersistenciaCupoIngresosError as auditoria:
                raise PersistenciaNuevaAtencionError("No fue posible guardar la auditoría del rechazo de cupo") from auditoria
        raise NuevaAtencionConflictoError(str(exc)) from exc
    except PersistenciaCupoIngresosError as exc:
        db.rollback()
        raise PersistenciaNuevaAtencionError("No fue posible validar el cupo diario") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaNuevaAtencionError("No fue posible generar la orden de nueva atención") from exc
