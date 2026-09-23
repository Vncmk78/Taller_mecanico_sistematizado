"""Modelo HistorialEstado (MS2: Vehículos, órdenes y capacidad).

MER (recuadro "BD MS2"):
  HISTORIAL_ESTADO(historial_id PK, orden_id FK, estado_anterior? FK,
                   estado_nuevo FK, actor_usuario_id? REF → MS1,
                   origen: usuario / sistema, fecha_hora, observacion?)

Cada fila es un cambio de estado de una orden (§4.2). La orden registra su
estado inicial aquí con `estado_anterior` vacío. Las filas solo se insertan: el
historial no se modifica ni se borra (trazabilidad).

- `estado_anterior` / `estado_nuevo`: FK al catálogo estado_orden.
- `actor_usuario_id`: referencia LÓGICA a MS1 (sin FK, §8). Vacío cuando el
  cambio lo hace el sistema.

Campos de auditoría (Semana 3) — responden quién, cuándo, qué y por qué:
- QUÉ:    estado_anterior → estado_nuevo.
- QUIÉN:  actor_usuario_id + origen. Si origen = 'usuario' el actor es
          obligatorio; si origen = 'sistema' el actor va vacío. Así nunca queda
          un cambio "hecho por un usuario" sin saber cuál.
- CUÁNDO: fecha_hora con zona horaria (timestamptz), la pone la base (now()).
- POR QUÉ: observacion opcional, pero si viene no puede ser solo espacios.
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
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms2_taller.db import Base

if TYPE_CHECKING:
    from services.ms2_taller.models.orden_trabajo import OrdenTrabajo


class HistorialEstado(Base):
    __tablename__ = "historial_estado"

    __table_args__ = (
        # Consulta típica: "historial de la orden X en orden cronológico".
        Index("ix_historial_estado_orden_fecha", "orden_id", "fecha_hora"),
        CheckConstraint("origen in ('usuario', 'sistema')", name="origen_valido"),
        # Un cambio de estado real: el nuevo estado debe ser distinto del anterior.
        CheckConstraint(
            "estado_anterior is null or estado_anterior <> estado_nuevo",
            name="cambio_real",
        ),
        CheckConstraint(
            "actor_usuario_id is null or actor_usuario_id > 0",
            name="actor_positivo",
        ),
        # Coherencia origen ↔ actor (auditoría de responsables).
        CheckConstraint(
            "(origen = 'usuario' and actor_usuario_id is not null) "
            "or (origen = 'sistema' and actor_usuario_id is null)",
            name="actor_segun_origen",
        ),
        CheckConstraint(
            "observacion is null or btrim(observacion) <> ''",
            name="observacion_no_vacia",
        ),
    )

    historial_id: Mapped[int] = mapped_column(primary_key=True)
    orden_id: Mapped[int] = mapped_column(
        ForeignKey("orden_trabajo.orden_id", ondelete="RESTRICT"),
        nullable=False,
    )
    estado_anterior: Mapped[int | None] = mapped_column(
        SmallInteger,
        ForeignKey("estado_orden.estado_codigo", ondelete="RESTRICT"),
        nullable=True,
    )
    estado_nuevo: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("estado_orden.estado_codigo", ondelete="RESTRICT"),
        nullable=False,
    )
    # REF lógica a Usuario (MS1). Sin ForeignKey a propósito (§8).
    actor_usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origen: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="usuario"
    )
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    orden: Mapped["OrdenTrabajo"] = relationship(back_populates="historial")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<HistorialEstado orden_id={self.orden_id} "
            f"{self.estado_anterior}->{self.estado_nuevo}>"
        )
