"""Creación y consultas iniciales de órdenes de trabajo.

Este módulo implementa únicamente el alcance de INT-32: alta en estado
``Recibido`` y visibilidad por recurso. La validación configurable del cupo
diario sigue pendiente según la sistematización y no se resuelve aquí.
"""

from __future__ import annotations

from sqlalchemy import false, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from services.ms2_taller.models.cliente import Cliente
from services.ms2_taller.models.estado_orden import RECIBIDO
from services.ms2_taller.models.historial_estado import HistorialEstado
from services.ms2_taller.models.ingreso_vehiculo import IngresoVehiculo
from services.ms2_taller.models.orden_trabajo import OrdenTrabajo
from services.ms2_taller.models.vehiculo import Vehiculo
from shared.auth import NombreRol, PrincipalAutenticado


class VehiculoNoEncontradoError(Exception):
    """El vehículo indicado para la nueva orden no existe."""


class OrdenNoEncontradaError(Exception):
    """La orden no existe o no es visible para la identidad autenticada."""


class PersistenciaOrdenError(Exception):
    """La operación sobre órdenes no pudo completarse de forma segura."""


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

        orden = OrdenTrabajo(
            vehiculo_id=vehiculo_id,
            ingreso_id=ingreso.ingreso_id,
            estado_codigo=RECIBIDO,
            mecanico_actual_id=None,
            creado_por_id=administrador_id,
        )
        db.add(orden)
        db.flush()

        db.add(
            HistorialEstado(
                orden_id=orden.orden_id,
                estado_anterior=None,
                estado_nuevo=RECIBIDO,
                actor_usuario_id=administrador_id,
                origen="usuario",
            )
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
