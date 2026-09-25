"""Modelos Proveedor y Repuesto (MS3: Presupuestos, repuestos y proveedores).

MER (recuadro "BD MS3"):
  PROVEEDOR(proveedor_id PK, nombre, contacto)
  REPUESTO(repuesto_id PK, proveedor_id FK, nombre, stock, umbral_particular?)

Relación 1:N FÍSICA (misma base MS3): un proveedor abastece varios repuestos y
cada repuesto tiene un proveedor.

`stock` es la cantidad física disponible. Se actualiza junto con cada
MovimientoInventario (ver inventario.py), que es el registro auditable de por qué
cambió. `umbral_particular` vacío significa "usar el umbral general" (§4.6).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms3_presupuestos.db import Base

if TYPE_CHECKING:
    from services.ms3_presupuestos.models.inventario import MovimientoInventario


class Proveedor(Base):
    __tablename__ = "proveedor"

    proveedor_id: Mapped[int] = mapped_column(primary_key=True)
    # Único: evita registrar dos veces el mismo proveedor.
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    # Teléfono, correo o persona de contacto (texto libre).
    contacto: Mapped[str] = mapped_column(String(200), nullable=False)

    repuestos: Mapped[list["Repuesto"]] = relationship(
        back_populates="proveedor",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Proveedor proveedor_id={self.proveedor_id} nombre={self.nombre!r}>"


class Repuesto(Base):
    __tablename__ = "repuesto"

    __table_args__ = (
        # Umbrales no negativos (§4.6). El stock nunca queda bajo cero: un consumo
        # que lo dejaría negativo debe rechazarse.
        CheckConstraint("stock >= 0", name="stock_no_negativo"),
        CheckConstraint(
            "umbral_particular is null or umbral_particular >= 0",
            name="umbral_no_negativo",
        ),
    )

    repuesto_id: Mapped[int] = mapped_column(primary_key=True)
    # RESTRICT: no se borra un proveedor que todavía tiene repuestos.
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedor.proveedor_id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    stock: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    umbral_particular: Mapped[int | None] = mapped_column(Integer, nullable=True)

    proveedor: Mapped["Proveedor"] = relationship(back_populates="repuestos")
    # Movimientos del repuesto. Sin cascada de borrado: son auditoría.
    movimientos: Mapped[list["MovimientoInventario"]] = relationship(
        back_populates="repuesto",
        cascade="save-update, merge",
        passive_deletes="all",
        lazy="select",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Repuesto repuesto_id={self.repuesto_id} stock={self.stock}>"
