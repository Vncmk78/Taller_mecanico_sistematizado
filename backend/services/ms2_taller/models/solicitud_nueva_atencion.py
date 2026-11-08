"""Solicitud distinta de la orden, según Sistematización §4.9."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from services.ms2_taller.db import Base


class SolicitudNuevaAtencion(Base):
    __tablename__ = "solicitud_nueva_atencion"
    __table_args__ = (
        CheckConstraint("cliente_usuario_id > 0", name="cliente_positivo"),
        CheckConstraint("revisor_id is null or revisor_id > 0", name="revisor_positivo"),
        CheckConstraint("btrim(descripcion) <> '' and length(descripcion) <= 2000", name="descripcion_valida"),
        CheckConstraint("situacion in ('pendiente', 'aceptada', 'rechazada')", name="situacion_valida"),
        CheckConstraint(
            "(situacion = 'pendiente' and respuesta is null and revisor_id is null and revisada_en is null) "
            "or (situacion in ('aceptada', 'rechazada') and respuesta is not null "
            "and btrim(respuesta) <> '' and revisor_id is not null and revisada_en is not null)",
            name="revision_coherente",
        ),
        CheckConstraint("revisada_en is null or revisada_en >= solicitada_en", name="fecha_revision_coherente"),
        CheckConstraint(
            "orden_generada_id is null or (situacion = 'aceptada' and orden_generada_id <> orden_cancelada_id)",
            name="orden_generada_coherente",
        ),
        # Índice A aprobado: una pendiente/aceptada por antecedente, incluso
        # después de generar orden. Las rechazadas se conservan y no bloquean.
        Index(
            "uq_nueva_atencion_vigente_por_orden", "orden_cancelada_id", unique=True,
            postgresql_where=text("situacion <> 'rechazada'"),
            sqlite_where=text("situacion <> 'rechazada'"),
        ),
        Index("ix_nueva_atencion_cliente_fecha", "cliente_usuario_id", "solicitada_en", "solicitud_id"),
    )

    solicitud_id: Mapped[int] = mapped_column(primary_key=True)
    orden_cancelada_id: Mapped[int] = mapped_column(
        ForeignKey("orden_trabajo.orden_id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    vehiculo_id: Mapped[int] = mapped_column(
        ForeignKey("vehiculo.vehiculo_id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    # Identidad y revisor son referencias lógicas a MS1, sin FK entre bases.
    cliente_usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    solicitada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    situacion: Mapped[str] = mapped_column(
        String(12), nullable=False, default="pendiente", server_default="pendiente",
    )
    respuesta: Mapped[str | None] = mapped_column(Text, nullable=True)
    revisor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revisada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    orden_generada_id: Mapped[int | None] = mapped_column(
        ForeignKey("orden_trabajo.orden_id", ondelete="RESTRICT"), nullable=True, index=True,
    )
