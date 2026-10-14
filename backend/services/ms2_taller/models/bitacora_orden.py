"""Modelos BitacoraOrden y BitacoraRepuesto (MS2: Vehículos, órdenes y capacidad).

La bitácora registra lo que el mecánico observa y ejecuta sobre una orden sin
depender de un cambio de estado: una observación (nota libre) o una acción
(trabajo realizado) que puede incluir repuestos utilizados.

MER (recuadro "BD MS2") no define esta tabla; se agrega como extensión aditiva
del flujo del mecánico (RF-11: evidencia del diagnóstico y trabajos realizados).

- `historial_estado` no sirve para estos registros: exige que el estado cambie
  (CHECK `cambio_real`). La bitácora no toca el estado de la orden.
- `autor_usuario_id` es una referencia LÓGICA a MS1 (sin FK, §8).
- `repuestos` es una tabla hija propia de MS2: NO referencia el catálogo de
  repuestos de MS3 (bases aisladas, §8); guarda el texto de lo utilizado.
- Las filas solo se insertan: la bitácora es trazabilidad y no se modifica ni
  se borra.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms2_taller.db import Base

if TYPE_CHECKING:
    from services.ms2_taller.models.orden_trabajo import OrdenTrabajo


class BitacoraOrden(Base):
    """Una entrada de la bitácora: observación o acción de la orden."""

    __tablename__ = "bitacora_orden"

    __table_args__ = (
        # Consulta típica: "bitácora de la orden X en orden cronológico".
        Index("ix_bitacora_orden_orden_creado", "orden_id", "creado_en"),
        CheckConstraint("tipo in ('observacion', 'accion')", name="tipo_valido"),
        CheckConstraint("autor_usuario_id > 0", name="autor_positivo"),
        CheckConstraint("btrim(descripcion) <> ''", name="descripcion_no_vacia"),
    )

    bitacora_id: Mapped[int] = mapped_column(primary_key=True)
    orden_id: Mapped[int] = mapped_column(
        ForeignKey("orden_trabajo.orden_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # REF lógica a Usuario (MS1). Sin ForeignKey a propósito (§8).
    autor_usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(12), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    orden: Mapped["OrdenTrabajo"] = relationship(back_populates="bitacora")
    # 1:N con los repuestos utilizados en una acción. Sin "delete" en la cascada:
    # igual que el resto de la trazabilidad, no se borra.
    repuestos: Mapped[list["BitacoraRepuesto"]] = relationship(
        back_populates="entrada",
        cascade="save-update, merge",
        passive_deletes="all",
        order_by="BitacoraRepuesto.repuesto_bitacora_id",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BitacoraOrden bitacora_id={self.bitacora_id} tipo={self.tipo}>"


class BitacoraRepuesto(Base):
    """Repuesto (texto libre y cantidad) utilizado en una acción de la bitácora."""

    __tablename__ = "bitacora_repuesto"

    __table_args__ = (
        CheckConstraint("btrim(nombre) <> ''", name="nombre_no_vacio"),
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
    )

    repuesto_bitacora_id: Mapped[int] = mapped_column(primary_key=True)
    bitacora_id: Mapped[int] = mapped_column(
        ForeignKey("bitacora_orden.bitacora_id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)

    entrada: Mapped["BitacoraOrden"] = relationship(back_populates="repuestos")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BitacoraRepuesto {self.cantidad}x {self.nombre}>"
