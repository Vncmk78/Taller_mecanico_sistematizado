"""Avisos persistentes generados por hechos de otros dominios en MS1."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms1_auth.db import Base

if TYPE_CHECKING:
    from services.ms1_auth.models.usuario import Usuario


class Notificacion(Base):
    """Un aviso lógico en la bandeja del usuario destinatario.

    `evento_id` es clave de idempotencia del productor (MS2). Las referencias
    de orden/vehículo son lógicas, pues esos recursos pertenecen a MS2.
    """

    __tablename__ = "notificacion"

    notificacion_id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False)
    destinatario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.usuario_id", ondelete="CASCADE"), index=True, nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    orden_id: Mapped[int] = mapped_column(Integer, nullable=False)
    vehiculo_id: Mapped[int] = mapped_column(Integer, nullable=False)
    titulo: Mapped[str] = mapped_column(String(120), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    destinatario: Mapped["Usuario"] = relationship()
