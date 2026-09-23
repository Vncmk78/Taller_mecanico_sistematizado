"""Modelo OrdenTrabajo (MS2: Vehículos, órdenes y capacidad).

MER (recuadro "BD MS2"):
  ORDEN_TRABAJO(orden_id PK, vehiculo_id FK, ingreso_id FK, estado_codigo FK,
                mecanico_actual_id? REF, creado_por_id REF,
                diagnostico_texto?, fecha_diagnostico?, diagnostico_autor_id? REF,
                entregado_en?, entregado_por_id? REF,
                devuelto_en?, devuelto_por_id? REF)

Relaciones:
- FÍSICAS (misma base MS2): vehiculo, ingreso, estado (catálogo) e historial.
- LÓGICAS (usuarios de MS1, sin FK, §8): mecánico actual, creador, autor del
  diagnóstico, quien entrega y quien devuelve.

Las órdenes NO se borran: cancelar es un cambio de estado (8 Cancelado). Por eso
todas las FK que salen de la orden son RESTRICT y el historial no se borra en
cascada.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms2_taller.db import Base
from services.ms2_taller.models.estado_orden import RECIBIDO

if TYPE_CHECKING:
    from services.ms2_taller.models.estado_orden import EstadoOrden
    from services.ms2_taller.models.historial_asignacion import HistorialAsignacion
    from services.ms2_taller.models.historial_estado import HistorialEstado
    from services.ms2_taller.models.ingreso_vehiculo import IngresoVehiculo
    from services.ms2_taller.models.vehiculo import Vehiculo


class OrdenTrabajo(Base):
    __tablename__ = "orden_trabajo"

    __table_args__ = (
        # Referencias lógicas a MS1: si vienen, deben ser ids positivos.
        CheckConstraint("creado_por_id > 0", name="creado_por_positivo"),
        CheckConstraint(
            "mecanico_actual_id is null or mecanico_actual_id > 0",
            name="mecanico_positivo",
        ),
        # Coherencia de pares "cuándo / quién": o están los dos o ninguno.
        CheckConstraint(
            "(diagnostico_texto is null) = (fecha_diagnostico is null) "
            "and (fecha_diagnostico is null) = (diagnostico_autor_id is null)",
            name="diagnostico_completo",
        ),
        CheckConstraint(
            "(entregado_en is null) = (entregado_por_id is null)",
            name="entrega_completa",
        ),
        CheckConstraint(
            "(devuelto_en is null) = (devuelto_por_id is null)",
            name="devolucion_completa",
        ),
        # Auditoría de fechas: ningún hito puede ser anterior a la creación.
        CheckConstraint(
            "(fecha_diagnostico is null or fecha_diagnostico >= creado_en) "
            "and (entregado_en is null or entregado_en >= creado_en) "
            "and (devuelto_en is null or devuelto_en >= creado_en)",
            name="fechas_coherentes",
        ),
    )

    orden_id: Mapped[int] = mapped_column(primary_key=True)

    vehiculo_id: Mapped[int] = mapped_column(
        ForeignKey("vehiculo.vehiculo_id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    ingreso_id: Mapped[int] = mapped_column(
        ForeignKey("ingreso_vehiculo.ingreso_id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    # Toda orden nace en "Recibido" (§4.2). Indexado: se filtra mucho por estado
    # (tablero del taller, carga activa de mecánicos).
    estado_codigo: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("estado_orden.estado_codigo", ondelete="RESTRICT"),
        index=True,
        nullable=False,
        default=RECIBIDO,
        server_default=str(RECIBIDO),
    )

    # --- Referencias lógicas a usuarios de MS1 (sin FK, §8) ---
    # La asignación puede estar vacía al recibir la orden (§4.7).
    mecanico_actual_id: Mapped[int | None] = mapped_column(
        Integer, index=True, nullable=True
    )
    creado_por_id: Mapped[int] = mapped_column(Integer, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # Auditoría (Semana 3): última modificación de la fila. El ORM lo renueva
    # en cada UPDATE (onupdate); la historia detallada está en los historiales.
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # --- Diagnóstico ---
    diagnostico_texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_diagnostico: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    diagnostico_autor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Entrega (término normal) y devolución (vehículo cancelado, §4.8) ---
    entregado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    entregado_por_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    devuelto_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    devuelto_por_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Relaciones ORM (todas dentro de MS2) ---
    vehiculo: Mapped["Vehiculo"] = relationship()
    ingreso: Mapped["IngresoVehiculo"] = relationship()
    estado: Mapped["EstadoOrden"] = relationship(lazy="joined")

    # 1:N con HistorialEstado, ordenado cronológicamente.
    #   - Sin "delete" en la cascada: el historial es trazabilidad y no se borra.
    #   - passive_deletes="all": el ORM no intenta poner orden_id en NULL; si se
    #     intenta borrar una orden con historial, la FK RESTRICT lo impide.
    historial: Mapped[list["HistorialEstado"]] = relationship(
        back_populates="orden",
        cascade="save-update, merge",
        passive_deletes="all",
        order_by="HistorialEstado.fecha_hora",
        lazy="selectin",
    )

    # 1:N con HistorialAsignacion (auditoría de responsables), misma política
    # que el historial de estados: no se borra.
    asignaciones: Mapped[list["HistorialAsignacion"]] = relationship(
        back_populates="orden",
        cascade="save-update, merge",
        passive_deletes="all",
        order_by="HistorialAsignacion.fecha_hora",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OrdenTrabajo orden_id={self.orden_id} estado={self.estado_codigo}>"
