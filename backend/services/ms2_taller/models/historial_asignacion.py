"""Modelo HistorialAsignacion (MS2: Vehículos, órdenes y capacidad).

MER (recuadro "BD MS2"):
  HISTORIAL_ASIGNACION(asignacion_id PK, orden_id FK,
                       mecanico_anterior_id? REF → MS1,
                       mecanico_nuevo_id REF → MS1,
                       administrador_id REF → MS1,
                       fecha_hora, observacion?)

Auditoría de RESPONSABLES (Semana 3): cada vez que el administrador asigna o
reasigna el mecánico de una orden queda una fila con quién estaba, quién quedó,
quién lo decidió y cuándo. `orden_trabajo.mecanico_actual_id` guarda solo el
valor vigente; la historia completa vive aquí. Las filas solo se insertan.
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
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms2_taller.db import Base

if TYPE_CHECKING:
    from services.ms2_taller.models.orden_trabajo import OrdenTrabajo


class HistorialAsignacion(Base):
    __tablename__ = "historial_asignacion"

    __table_args__ = (
        Index("ix_historial_asignacion_orden_fecha", "orden_id", "fecha_hora"),
        CheckConstraint(
            "mecanico_nuevo_id > 0 and administrador_id > 0 "
            "and (mecanico_anterior_id is null or mecanico_anterior_id > 0)",
            name="ids_positivos",
        ),
        # Reasignar al mismo mecánico no es un cambio.
        CheckConstraint(
            "mecanico_anterior_id is null or mecanico_anterior_id <> mecanico_nuevo_id",
            name="cambio_real",
        ),
        CheckConstraint(
            "observacion is null or btrim(observacion) <> ''",
            name="observacion_no_vacia",
        ),
    )

    asignacion_id: Mapped[int] = mapped_column(primary_key=True)
    orden_id: Mapped[int] = mapped_column(
        ForeignKey("orden_trabajo.orden_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # REF lógicas a Usuario (MS1). Sin ForeignKey a propósito (§8).
    mecanico_anterior_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mecanico_nuevo_id: Mapped[int] = mapped_column(Integer, nullable=False)
    administrador_id: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    orden: Mapped["OrdenTrabajo"] = relationship(back_populates="asignaciones")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<HistorialAsignacion orden_id={self.orden_id} "
            f"{self.mecanico_anterior_id}->{self.mecanico_nuevo_id}>"
        )
