"""Outbox propia de MS3; el envío nunca mantiene una transacción distribuida."""

from datetime import datetime
from uuid import UUID
from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from services.ms3_presupuestos.db import Base


class EventoAvisoOutbox(Base):
    __tablename__ = "evento_aviso_outbox"
    __table_args__ = (CheckConstraint("intentos >= 0", name="intentos_aviso_no_negativos"),)
    outbox_id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    proxima_tentativa_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_error: Mapped[str | None] = mapped_column(String(300))
