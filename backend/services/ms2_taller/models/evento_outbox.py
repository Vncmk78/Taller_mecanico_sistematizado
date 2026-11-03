"""Outbox transaccional de eventos de dominio producidos por MS2."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, JSON, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from services.ms2_taller.db import Base


class EventoOutbox(Base):
    """Evento pendiente para publicar a MS1 sin perder la atomicidad del dominio."""

    __tablename__ = "evento_outbox"
    __table_args__ = (
        CheckConstraint("intentos >= 0", name="intentos_no_negativos"),
        Index(
            "ix_evento_outbox_pendiente",
            "proxima_tentativa_en",
            "outbox_id",
            postgresql_where=text("publicado_en is null"),
        ),
    )

    outbox_id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    proxima_tentativa_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ultimo_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
