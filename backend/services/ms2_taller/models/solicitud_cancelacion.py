"""Solicitud auditable de cancelación de una orden (Sistematización §4.8)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from services.ms2_taller.db import Base


class SolicitudCancelacion(Base):
    __tablename__ = "solicitud_cancelacion"

    __table_args__ = (
        UniqueConstraint("orden_id", name="uq_solicitud_cancelacion_orden"),
        CheckConstraint("cliente_usuario_id > 0", name="cliente_positivo"),
        CheckConstraint(
            "administrador_id is null or administrador_id > 0",
            name="administrador_positivo",
        ),
        CheckConstraint("estado_al_solicitar in (1, 2, 3)", name="estado_cancelable"),
        CheckConstraint("estado in ('pendiente', 'confirmada')", name="estado_valido"),
        CheckConstraint(
            "(estado = 'pendiente' and administrador_id is null and confirmada_en is null) "
            "or (estado = 'confirmada' and administrador_id is not null "
            "and confirmada_en is not null)",
            name="confirmacion_coherente",
        ),
        CheckConstraint("btrim(motivo) <> ''", name="motivo_no_vacio"),
    )

    solicitud_id: Mapped[int] = mapped_column(primary_key=True)
    orden_id: Mapped[int] = mapped_column(
        ForeignKey("orden_trabajo.orden_id", ondelete="RESTRICT"), nullable=False
    )
    # Referencias lógicas a MS1: no hay FK entre microservicios (§8).
    cliente_usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    estado_al_solicitar: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default="pendiente"
    )
    solicitada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    administrador_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
