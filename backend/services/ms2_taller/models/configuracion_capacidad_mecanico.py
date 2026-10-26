"""Configuración y auditoría de capacidad de órdenes por mecánico (MS2)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from services.ms2_taller.db import Base


class ConfiguracionCapacidadMecanico(Base):
    """Fila singleton con el límite vigente de órdenes activas por mecánico."""

    __tablename__ = "configuracion_capacidad_mecanico"
    __table_args__ = (
        CheckConstraint("configuracion_id = 1", name="singleton"),
        CheckConstraint(
            "max_ordenes_activas is null or max_ordenes_activas > 0",
            name="maximo_positivo",
        ),
        CheckConstraint(
            "actualizado_por_id is null or actualizado_por_id > 0",
            name="administrador_positivo",
        ),
    )

    configuracion_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    max_ordenes_activas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actualizado_por_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class HistorialConfiguracionCapacidadMecanico(Base):
    """Valores anterior/nuevo y administrador de cada cambio de capacidad."""

    __tablename__ = "historial_configuracion_capacidad_mecanico"
    __table_args__ = (
        CheckConstraint(
            "valor_nuevo > 0 and administrador_id > 0 "
            "and (valor_anterior is null or "
            "(valor_anterior > 0 and valor_anterior <> valor_nuevo))",
            name="valores_positivos",
        ),
    )

    historial_id: Mapped[int] = mapped_column(primary_key=True)
    valor_anterior: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valor_nuevo: Mapped[int] = mapped_column(Integer, nullable=False)
    administrador_id: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class HistorialValidacionCapacidadMecanico(Base):
    """Resultado auditable de cada validación al asignar o reasignar una orden."""

    __tablename__ = "historial_validacion_capacidad_mecanico"
    __table_args__ = (
        Index("ix_validacion_capacidad_orden_fecha", "orden_id", "fecha_hora"),
        Index("ix_validacion_capacidad_mecanico_fecha", "mecanico_id", "fecha_hora"),
        CheckConstraint(
            "orden_id > 0 and mecanico_id > 0 and administrador_id > 0 "
            "and ordenes_activas >= 0 "
            "and (max_ordenes_activas is null or max_ordenes_activas > 0) "
            "and (mecanico_anterior_id is null or mecanico_anterior_id > 0) "
            "and ((aceptada and resultado = 'capacidad_disponible') or "
            "(not aceptada and resultado in "
            "('capacidad_excedida', 'capacidad_no_configurada')))",
            name="datos_validos",
        ),
    )

    validacion_id: Mapped[int] = mapped_column(primary_key=True)
    orden_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("orden_trabajo.orden_id", ondelete="RESTRICT"),
        nullable=False,
    )
    mecanico_anterior_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mecanico_id: Mapped[int] = mapped_column(Integer, nullable=False)
    administrador_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ordenes_activas: Mapped[int] = mapped_column(Integer, nullable=False)
    max_ordenes_activas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aceptada: Mapped[bool] = mapped_column(nullable=False)
    resultado: Mapped[str] = mapped_column(nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
