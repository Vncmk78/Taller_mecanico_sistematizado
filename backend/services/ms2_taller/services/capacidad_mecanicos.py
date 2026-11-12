"""Casos de uso para configurar y consultar la capacidad de mecánicos en MS2."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from services.ms2_taller.models.configuracion_capacidad_mecanico import (
    ConfiguracionCapacidadMecanico,
    HistorialConfiguracionCapacidadMecanico,
    HistorialValidacionCapacidadMecanico,
)
from services.ms2_taller.models.estado_orden import CANCELADO, ENTREGADO
from services.ms2_taller.models.orden_trabajo import OrdenTrabajo


class CapacidadMecanicoNoConfiguradaError(Exception):
    """Aún no se ha configurado el máximo por mecánico."""


class CapacidadMecanicoExcedidaError(Exception):
    """El mecánico de destino ya alcanzó el máximo de órdenes activas."""


class PersistenciaCapacidadError(Exception):
    """No fue posible consultar o guardar la configuración de capacidad."""


def _contar_ordenes_activas(db: Session, mecanico_id: int) -> int:
    consulta = (
        select(func.count())
        .select_from(OrdenTrabajo)
        .where(
            OrdenTrabajo.mecanico_actual_id == mecanico_id,
            OrdenTrabajo.estado_codigo.not_in((ENTREGADO, CANCELADO)),
        )
    )
    return int(db.scalar(consulta) or 0)


def obtener_configuracion_capacidad_mecanicos(
    db: Session,
) -> tuple[ConfiguracionCapacidadMecanico, list[dict[str, int]]]:
    """Devuelve el límite y los mecánicos que superan ese valor, si los hay."""

    try:
        configuracion = db.get(ConfiguracionCapacidadMecanico, 1)
        if configuracion is None:
            # Facilita la ejecución en bases creadas desde metadata; producción
            # inserta la misma fila singleton mediante la migración.
            configuracion = ConfiguracionCapacidadMecanico(configuracion_id=1)
            db.add(configuracion)
            db.flush()
            db.commit()
        sobre_limite = _mecanicos_sobre_limite(
            db, configuracion.max_ordenes_activas
        )
        return configuracion, sobre_limite
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaCapacidadError(
            "No fue posible consultar la capacidad de los mecánicos"
        ) from exc


def configurar_capacidad_mecanicos(
    db: Session,
    *,
    max_ordenes_activas: int,
    administrador_id: int,
) -> tuple[ConfiguracionCapacidadMecanico, list[dict[str, int]]]:
    """Actualiza el máximo y registra el valor anterior y el administrador."""

    try:
        configuracion = db.scalar(
            select(ConfiguracionCapacidadMecanico)
            .where(ConfiguracionCapacidadMecanico.configuracion_id == 1)
            .with_for_update()
        )
        if configuracion is None:
            configuracion = ConfiguracionCapacidadMecanico(configuracion_id=1)
            db.add(configuracion)
            db.flush()

        valor_anterior = configuracion.max_ordenes_activas
        if valor_anterior != max_ordenes_activas:
            db.add(
                HistorialConfiguracionCapacidadMecanico(
                    valor_anterior=valor_anterior,
                    valor_nuevo=max_ordenes_activas,
                    administrador_id=administrador_id,
                )
            )
            configuracion.max_ordenes_activas = max_ordenes_activas
            configuracion.actualizado_por_id = administrador_id
        db.flush()
        db.refresh(configuracion)
        sobre_limite = _mecanicos_sobre_limite(db, max_ordenes_activas)
        db.commit()
        return configuracion, sobre_limite
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaCapacidadError(
            "No fue posible configurar la capacidad de los mecánicos"
        ) from exc


def validar_capacidad_para_asignacion(
    db: Session,
    *,
    orden_id: int,
    mecanico_anterior_id: int | None,
    mecanico_id: int,
    administrador_id: int,
) -> None:
    """Bloquea la configuración mientras cuenta y registra la validación.

    La fila singleton serializa las asignaciones entre transacciones de MS2.
    El conteo posterior al bloqueo impide que dos solicitudes simultáneas
    ocupen el último cupo del mismo mecánico.
    """

    configuracion = db.scalar(
        select(ConfiguracionCapacidadMecanico)
        .where(ConfiguracionCapacidadMecanico.configuracion_id == 1)
        .with_for_update()
    )
    maximo = configuracion.max_ordenes_activas if configuracion else None
    ordenes_activas = _contar_ordenes_activas(db, mecanico_id)

    if maximo is None:
        db.add(
            HistorialValidacionCapacidadMecanico(
                orden_id=orden_id,
                mecanico_anterior_id=mecanico_anterior_id,
                mecanico_id=mecanico_id,
                administrador_id=administrador_id,
                ordenes_activas=ordenes_activas,
                max_ordenes_activas=None,
                aceptada=False,
                resultado="capacidad_no_configurada",
            )
        )
        db.commit()
        raise CapacidadMecanicoNoConfiguradaError(
            "Configura el máximo de órdenes activas por mecánico antes de asignar"
        )

    if ordenes_activas >= maximo:
        db.add(
            HistorialValidacionCapacidadMecanico(
                orden_id=orden_id,
                mecanico_anterior_id=mecanico_anterior_id,
                mecanico_id=mecanico_id,
                administrador_id=administrador_id,
                ordenes_activas=ordenes_activas,
                max_ordenes_activas=maximo,
                aceptada=False,
                resultado="capacidad_excedida",
            )
        )
        db.commit()
        raise CapacidadMecanicoExcedidaError(
            "El mecánico ya alcanzó el máximo de órdenes activas"
        )

    db.add(
        HistorialValidacionCapacidadMecanico(
            orden_id=orden_id,
            mecanico_anterior_id=mecanico_anterior_id,
            mecanico_id=mecanico_id,
            administrador_id=administrador_id,
            ordenes_activas=ordenes_activas,
            max_ordenes_activas=maximo,
            aceptada=True,
            resultado="capacidad_disponible",
        )
    )


def _mecanicos_sobre_limite(
    db: Session,
    maximo: int | None,
) -> list[dict[str, int]]:
    if maximo is None:
        return []
    consulta = (
        select(
            OrdenTrabajo.mecanico_actual_id,
            func.count().label("ordenes_activas"),
        )
        .where(
            OrdenTrabajo.mecanico_actual_id.is_not(None),
            OrdenTrabajo.estado_codigo.not_in((ENTREGADO, CANCELADO)),
        )
        .group_by(OrdenTrabajo.mecanico_actual_id)
        .having(func.count() > maximo)
        .order_by(OrdenTrabajo.mecanico_actual_id)
    )
    return [
        {"mecanico_id": int(mecanico_id), "ordenes_activas": int(cantidad)}
        for mecanico_id, cantidad in db.execute(consulta)
    ]
