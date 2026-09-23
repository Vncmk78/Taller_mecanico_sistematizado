"""Modelos de presupuesto (MS3: Presupuestos, repuestos y proveedores).

MER (recuadro "BD MS3"):
  PRESUPUESTO(presupuesto_id PK, orden_id UK/REF → MS2, creado_en)
  VERSION_PRESUPUESTO(version_id PK, presupuesto_id FK,
                      UK (presupuesto_id, numero), creado_en, enviado_en?,
                      creado_por_id REF → MS1)
  ITEM_PRESUPUESTO(item_id PK, version_id FK, tipo: repuesto / mano_de_obra,
                   repuesto_id? FK, descripcion, cantidad, precio_unitario)

Idea central (§4.3): el presupuesto es UNO por orden y lo que cambia son sus
VERSIONES. Una corrección no edita la versión enviada: crea otra versión con el
número siguiente. Los ítems cuelgan de la versión, no del presupuesto.

El bloqueo de la versión aprobada y la decisión del cliente se agregan en la
tarea "Definir estructura de versionado de presupuestos y bloqueo de la versión
aprobada" (Semana 3).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms3_presupuestos.db import Base

if TYPE_CHECKING:
    from services.ms3_presupuestos.models.proveedor import Repuesto


class Presupuesto(Base):
    __tablename__ = "presupuesto"

    __table_args__ = (
        CheckConstraint("orden_id > 0", name="orden_positiva"),
    )

    presupuesto_id: Mapped[int] = mapped_column(primary_key=True)
    # REF lógica a OrdenTrabajo (MS2). Única: un presupuesto por orden.
    # Sin ForeignKey a propósito (§8): la orden vive en otra base.
    orden_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Versiones en orden (1, 2, 3...). Sin borrado en cascada: las versiones
    # enviadas se conservan (§4.3).
    versiones: Mapped[list["VersionPresupuesto"]] = relationship(
        back_populates="presupuesto",
        cascade="save-update, merge",
        passive_deletes="all",
        order_by="VersionPresupuesto.numero",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Presupuesto presupuesto_id={self.presupuesto_id} orden_id={self.orden_id}>"


class VersionPresupuesto(Base):
    __tablename__ = "version_presupuesto"

    __table_args__ = (
        # No puede haber dos "versión 2" del mismo presupuesto.
        UniqueConstraint("presupuesto_id", "numero"),
        CheckConstraint("numero >= 1", name="numero_positivo"),
        CheckConstraint("creado_por_id > 0", name="creado_por_positivo"),
        CheckConstraint(
            "enviado_en is null or enviado_en >= creado_en",
            name="envio_posterior",
        ),
    )

    version_id: Mapped[int] = mapped_column(primary_key=True)
    # El índice lo cubre la UK (presupuesto_id, numero): empieza por presupuesto_id.
    presupuesto_id: Mapped[int] = mapped_column(
        ForeignKey("presupuesto.presupuesto_id", ondelete="RESTRICT"),
        nullable=False,
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    # REF lógica a Usuario (MS1).
    creado_por_id: Mapped[int] = mapped_column(Integer, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    enviado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    presupuesto: Mapped["Presupuesto"] = relationship(back_populates="versiones")
    # Los ítems SÍ se manejan junto con su versión (se crean con ella).
    items: Mapped[list["ItemPresupuesto"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VersionPresupuesto presupuesto_id={self.presupuesto_id} numero={self.numero}>"


class ItemPresupuesto(Base):
    __tablename__ = "item_presupuesto"

    __table_args__ = (
        CheckConstraint(
            "tipo in ('repuesto', 'mano_de_obra')", name="tipo_valido"
        ),
        # repuesto_id obligatorio para repuestos y vacío en mano de obra (MER).
        CheckConstraint(
            "(tipo = 'repuesto') = (repuesto_id is not null)",
            name="repuesto_segun_tipo",
        ),
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="precio_no_negativo"),
    )

    item_id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("version_presupuesto.version_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(12), nullable=False)
    repuesto_id: Mapped[int | None] = mapped_column(
        ForeignKey("repuesto.repuesto_id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    # Numeric: la mano de obra puede cobrarse en fracciones de hora (1.5 h) y el
    # dinero nunca se guarda en float (errores de redondeo).
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    version: Mapped["VersionPresupuesto"] = relationship(back_populates="items")
    repuesto: Mapped["Repuesto | None"] = relationship()

    @property
    def subtotal(self) -> Decimal:
        """cantidad × precio_unitario (calculado, no se guarda)."""
        return self.cantidad * self.precio_unitario

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ItemPresupuesto {self.tipo} {self.descripcion!r}>"
