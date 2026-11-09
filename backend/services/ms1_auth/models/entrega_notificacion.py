"""Dispositivos e intentos por canal, únicamente en la base de MS1."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from services.ms1_auth.db import Base


class DispositivoPush(Base):
    __tablename__ = "dispositivo_push"
    dispositivo_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.usuario_id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    plataforma: Mapped[str] = mapped_column(String(20), nullable=False)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EntregaNotificacion(Base):
    __tablename__ = "entrega_notificacion"
    __table_args__ = (
        CheckConstraint("canal IN ('correo','push')", name="canal_valido"),
        CheckConstraint(
            "estado IN ('pendiente','procesando','aceptada','fallida','sin_configuracion','sin_dispositivo','omitida')",
            name="estado_entrega_valido",
        ),
        CheckConstraint("intentos >= 0", name="intentos_entrega_no_negativos"),
    )
    entrega_id: Mapped[int] = mapped_column(primary_key=True)
    notificacion_id: Mapped[int] = mapped_column(
        ForeignKey("notificacion.notificacion_id", ondelete="CASCADE"), index=True, nullable=False
    )
    dispositivo_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dispositivo_push.dispositivo_id", ondelete="SET NULL"), index=True
    )
    clave: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    canal: Mapped[str] = mapped_column(String(10), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pendiente", server_default="pendiente"
    )
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    proxima_tentativa_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    lease_token: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    lease_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aceptada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_error: Mapped[str | None] = mapped_column(String(80))
    proveedor_id: Mapped[str | None] = mapped_column(String(300))
    notificacion: Mapped["Notificacion"] = relationship("Notificacion")


class IntentoEntrega(Base):
    __tablename__ = "intento_entrega"
    __table_args__ = (UniqueConstraint("entrega_id", "numero", name="uq_intento_entrega_numero"),)
    intento_id: Mapped[int] = mapped_column(primary_key=True)
    entrega_id: Mapped[int] = mapped_column(
        ForeignKey("entrega_notificacion.entrega_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    iniciado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finalizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[str] = mapped_column(
        String(24), nullable=False, default="procesando", server_default="procesando"
    )
    codigo_error: Mapped[str | None] = mapped_column(String(80))
