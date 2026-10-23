"""Configuración y auditoría del cupo diario de ingresos físicos en MS2."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from services.ms2_taller.db import Base


class ConfiguracionCupoIngresos(Base):
    """Fila singleton con el máximo diario de ingresos físicos."""

    __tablename__ = "configuracion_cupo_ingresos"
    __table_args__ = (
        CheckConstraint("configuracion_id = 1", name="singleton"),
        CheckConstraint(
            "max_ingresos_diarios is null or max_ingresos_diarios > 0",
            name="maximo_positivo",
        ),
        CheckConstraint(
            "actualizado_por_id is null or actualizado_por_id > 0",
            name="administrador_positivo",
        ),
    )

    configuracion_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    max_ingresos_diarios: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actualizado_por_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )


class HistorialConfiguracionCupoIngresos(Base):
    """Valores anterior/nuevo y administrador de cada cambio de cupo diario."""

    __tablename__ = "historial_configuracion_cupo_ingresos"
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


class HistorialValidacionCupoIngreso(Base):
    """Intento de ingreso con jornada local, límite y resultado usados."""

    __tablename__ = "historial_validacion_cupo_ingreso"
    __table_args__ = (
        Index("ix_validacion_cupo_jornada", "jornada_local", "fecha_hora"),
        Index("ix_validacion_cupo_vehiculo", "vehiculo_id", "fecha_hora"),
        CheckConstraint(
            "vehiculo_id > 0 and administrador_id > 0 and ingresos_registrados >= 0 "
            "and (max_ingresos_diarios is null or max_ingresos_diarios > 0) "
            "and (ingreso_id is null or ingreso_id > 0) "
            "and ((aceptada and resultado = 'cupo_disponible' and ingreso_id is not null) "
            "or (not aceptada and resultado in "
            "('cupo_excedido', 'cupo_no_configurado') and ingreso_id is null))",
            name="datos_validos",
        ),
    )

    validacion_id: Mapped[int] = mapped_column(primary_key=True)
    vehiculo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehiculo.vehiculo_id", ondelete="RESTRICT"), nullable=False
    )
    ingreso_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ingreso_vehiculo.ingreso_id", ondelete="RESTRICT"),
        nullable=True,
    )
    jornada_local: Mapped[date] = mapped_column(Date, nullable=False)
    ingresos_registrados: Mapped[int] = mapped_column(Integer, nullable=False)
    max_ingresos_diarios: Mapped[int | None] = mapped_column(Integer, nullable=True)
    administrador_id: Mapped[int] = mapped_column(Integer, nullable=False)
    aceptada: Mapped[bool] = mapped_column(Boolean, nullable=False)
    resultado: Mapped[str] = mapped_column(String(length=40), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
