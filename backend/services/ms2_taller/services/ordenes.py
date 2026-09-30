"""Creación, consulta y asociación inicial de órdenes de trabajo.

INT-32 aporta el alta en estado ``Recibido`` y la visibilidad por recurso.
INT-33 agrega la asignación y reasignación auditada del mecánico. La primera
asignación de una orden recibida la deja esperando diagnóstico; las posteriores
no cambian automáticamente el estado. La validación remota del rol del destino
y la capacidad configurable siguen pendientes porque su infraestructura todavía
no está disponible.
"""

from __future__ import annotations

from sqlalchemy import false, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from services.ms2_taller.domain.transiciones_orden import (
    EventoOrden,
    TransicionOrdenTerminalError,
    resolver_transicion,
    validar_estado_no_terminal,
)
from services.ms2_taller.models.cliente import Cliente
from services.ms2_taller.models.estado_orden import RECIBIDO
from services.ms2_taller.models.historial_asignacion import HistorialAsignacion
from services.ms2_taller.models.historial_estado import HistorialEstado
from services.ms2_taller.models.ingreso_vehiculo import IngresoVehiculo
from services.ms2_taller.models.orden_trabajo import OrdenTrabajo
from services.ms2_taller.models.vehiculo import Vehiculo
from shared.auth import NombreRol, PrincipalAutenticado


class VehiculoNoEncontradoError(Exception):
    """El vehículo indicado para la nueva orden no existe."""


class OrdenNoEncontradaError(Exception):
    """La orden no existe o no es visible para la identidad autenticada."""


class OrdenTerminalError(Exception):
    """Una orden entregada o cancelada ya no admite cambios de responsable."""


class PersistenciaOrdenError(Exception):
    """La operación sobre órdenes no pudo completarse de forma segura."""


def registrar_historial_estado(
    db: Session,
    *,
    orden_id: int,
    estado_anterior: int | None,
    estado_nuevo: int,
    actor_usuario_id: int | None,
    origen: str,
    observacion: str | None = None,
) -> HistorialEstado:
    """Agrega el cambio de estado a la sesión sin confirmar la transacción.

    La base genera la fecha/hora y aplica las restricciones del modelo. La
    operación que invoca esta función controla flush, commit y rollback para
    persistir el historial junto con el resto de sus cambios de forma atómica.
    """

    historial = HistorialEstado(
        orden_id=orden_id,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        actor_usuario_id=actor_usuario_id,
        origen=origen,
        observacion=observacion,
    )
    db.add(historial)
    return historial


def _consulta_orden_para_actualizacion(
    orden_id: int,
) -> Select[tuple[OrdenTrabajo]]:
    """Selecciona y bloquea la orden cuyo responsable se modificará."""

    return (
        select(OrdenTrabajo)
        .where(OrdenTrabajo.orden_id == orden_id)
        # OrdenTrabajo carga EstadoOrden con un LEFT JOIN. Limitar el lock a la
        # tabla de órdenes evita que PostgreSQL intente bloquear el lado nullable
        # del join y expresa exactamente la fila que protege esta operación.
        .with_for_update(of=OrdenTrabajo)
    )


def _consulta_vehiculo_para_actualizacion(
    vehiculo_id: int,
) -> Select[tuple[Vehiculo]]:
    """Selecciona y bloquea solo el vehículo cuya estancia se decidirá."""

    return (
        select(Vehiculo)
        .where(Vehiculo.vehiculo_id == vehiculo_id)
        .with_for_update()
    )


def crear_orden(
    db: Session,
    vehiculo_id: int,
    administrador_id: int,
) -> OrdenTrabajo:
    """Crea ingreso, orden e historial inicial dentro de una transacción.

    Si ya existe una estancia abierta para el vehículo, se reutiliza. La
    comprobación del cupo diario configurable queda deliberadamente pendiente.
    """

    try:
        # PostgreSQL conserva este bloqueo de fila hasta el commit/rollback. Así
        # dos altas del mismo vehículo no pueden decidir en paralelo que falta
        # un ingreso abierto; vehículos distintos usan filas y locks distintos.
        vehiculo = db.scalar(_consulta_vehiculo_para_actualizacion(vehiculo_id))
        if vehiculo is None:
            raise VehiculoNoEncontradoError("Vehículo no encontrado")

        ingreso = db.scalar(
            select(IngresoVehiculo)
            .where(
                IngresoVehiculo.vehiculo_id == vehiculo_id,
                IngresoVehiculo.salida_en.is_(None),
            )
            .order_by(
                IngresoVehiculo.fecha_hora.desc(),
                IngresoVehiculo.ingreso_id.desc(),
            )
            .limit(1)
        )
        if ingreso is None:
            ingreso = IngresoVehiculo(
                vehiculo_id=vehiculo_id,
                registrado_por_id=administrador_id,
            )
            db.add(ingreso)
            db.flush()

        estado_inicial = resolver_transicion(None, EventoOrden.CREACION)
        orden = OrdenTrabajo(
            vehiculo_id=vehiculo_id,
            ingreso_id=ingreso.ingreso_id,
            estado_codigo=estado_inicial,
            mecanico_actual_id=None,
            creado_por_id=administrador_id,
        )
        db.add(orden)
        db.flush()

        registrar_historial_estado(
            db,
            orden_id=orden.orden_id,
            estado_anterior=None,
            estado_nuevo=estado_inicial,
            actor_usuario_id=administrador_id,
            origen="usuario",
        )
        db.flush()
        db.refresh(orden)
        db.commit()
        return orden
    except VehiculoNoEncontradoError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError("No fue posible crear la orden") from exc


def asignar_mecanico(
    db: Session,
    *,
    orden_id: int,
    mecanico_id: int,
    administrador_id: int,
    observacion: str | None = None,
) -> OrdenTrabajo:
    """Asigna o reasigna el mecánico y conserva el cambio en una transacción.

    El bloqueo de la orden se mantiene hasta el commit o rollback. De este modo,
    una operación concurrente sobre la misma orden observa el responsable que
    haya confirmado la operación anterior. En la primera asignación, una orden
    ``Recibida`` pasa a ``Esperando diagnóstico`` y se auditan ambos cambios.
    La comprobación remota del rol del destino y la capacidad configurable quedan
    deliberadamente fuera de INT-33.
    """

    try:
        orden = db.scalar(_consulta_orden_para_actualizacion(orden_id))
        if orden is None:
            raise OrdenNoEncontradaError("Orden no encontrada")
        try:
            validar_estado_no_terminal(orden.estado_codigo)
        except TransicionOrdenTerminalError as exc:
            raise OrdenTerminalError(
                "No se puede cambiar el mecánico de una orden terminal"
            ) from exc

        mecanico_anterior_id = orden.mecanico_actual_id
        if mecanico_anterior_id == mecanico_id:
            # No hay cambio que auditar. El commit libera explícitamente el lock
            # sin emitir UPDATE ni insertar una fila de historial.
            db.commit()
            return orden

        orden.mecanico_actual_id = mecanico_id
        db.add(
            HistorialAsignacion(
                orden_id=orden.orden_id,
                mecanico_anterior_id=mecanico_anterior_id,
                mecanico_nuevo_id=mecanico_id,
                administrador_id=administrador_id,
                observacion=observacion,
            )
        )

        if mecanico_anterior_id is None and orden.estado_codigo == RECIBIDO:
            estado_nuevo = resolver_transicion(
                orden.estado_codigo,
                EventoOrden.PRIMERA_ASIGNACION,
            )
            orden.estado_codigo = estado_nuevo
            registrar_historial_estado(
                db,
                orden_id=orden.orden_id,
                estado_anterior=RECIBIDO,
                estado_nuevo=estado_nuevo,
                actor_usuario_id=administrador_id,
                origen="usuario",
            )

        db.flush()
        db.refresh(orden)
        db.commit()
        return orden
    except OrdenNoEncontradaError:
        db.rollback()
        raise
    except OrdenTerminalError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError(
            "No fue posible asignar el mecánico"
        ) from exc


def listar_ordenes(
    db: Session,
    principal: PrincipalAutenticado,
) -> list[OrdenTrabajo]:
    """Lista la unión de órdenes visibles para todos los roles del principal."""

    try:
        consulta = select(OrdenTrabajo).order_by(OrdenTrabajo.orden_id)
        filtro = _filtro_visibilidad(principal)
        if filtro is not None:
            consulta = consulta.where(filtro)
        return list(db.scalars(consulta).unique().all())
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError("No fue posible consultar las órdenes") from exc


def obtener_orden_visible(
    db: Session,
    principal: PrincipalAutenticado,
    orden_id: int,
) -> OrdenTrabajo:
    """Obtiene una orden sin revelar si una orden no visible realmente existe."""

    try:
        consulta = select(OrdenTrabajo).where(OrdenTrabajo.orden_id == orden_id)
        filtro = _filtro_visibilidad(principal)
        if filtro is not None:
            consulta = consulta.where(filtro)
        orden = db.scalar(consulta)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError("No fue posible consultar la orden") from exc

    if orden is None:
        raise OrdenNoEncontradaError("Orden no encontrada")
    return orden


def _filtro_visibilidad(
    principal: PrincipalAutenticado,
) -> ColumnElement[bool] | None:
    """Construye la autorización por recurso específica del dominio órdenes."""

    if NombreRol.ADMINISTRADOR in principal.roles:
        return None

    alcances = []
    if NombreRol.CLIENTE in principal.roles:
        alcances.append(
            OrdenTrabajo.vehiculo.has(
                Vehiculo.cliente.has(Cliente.usuario_id == principal.usuario_id)
            )
        )
    if NombreRol.MECANICO in principal.roles:
        alcances.append(OrdenTrabajo.mecanico_actual_id == principal.usuario_id)

    return or_(*alcances) if alcances else false()
