"""Modelos ORM del microservicio MS3 (Presupuestos, Repuestos y Proveedores).

Fuente: lámina 04-mer-erd, recuadro "BD MS3", y Sistematización final §4.3
(presupuestos) y §4.6 (inventario y umbrales).

Aislamiento de datos (§8): NO existen claves foráneas físicas hacia otras bases.
Las referencias a MS1 (usuarios) y MS2 (órdenes) se guardan como enteros sueltos
(marcados REF en el MER) y se resuelven por contrato de API, nunca con ForeignKey.
Las FK físicas solo se usan dentro de esta misma base (p. ej. Repuesto->Proveedor).
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base


class Proveedor(Base):
    __tablename__ = "proveedor"

    proveedor_id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    contacto: Mapped[str | None] = mapped_column(String(150), nullable=True)

    repuestos: Mapped[list["Repuesto"]] = relationship(back_populates="proveedor")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Proveedor proveedor_id={self.proveedor_id} nombre={self.nombre!r}>"


class Repuesto(Base):
    __tablename__ = "repuesto"

    repuesto_id: Mapped[int] = mapped_column(primary_key=True)
    # FK física local: Proveedor vive en la MISMA base (MS3).
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedor.proveedor_id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Umbral propio del repuesto; si es NULL rige el umbral general (§4.6).
    umbral_particular: Mapped[int | None] = mapped_column(Integer, nullable=True)

    proveedor: Mapped["Proveedor"] = relationship(back_populates="repuestos")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Repuesto repuesto_id={self.repuesto_id} nombre={self.nombre!r}>"


class Presupuesto(Base):
    __tablename__ = "presupuesto"

    presupuesto_id: Mapped[int] = mapped_column(primary_key=True)
    # REF lógica a la Orden de Trabajo (MS2). Único: 1 orden <-> 1 presupuesto.
    # Sin ForeignKey a propósito (§8): la referencia cruza de base.
    orden_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Presupuesto presupuesto_id={self.presupuesto_id} orden_id={self.orden_id}>"


class ParametroInventario(Base):
    __tablename__ = "parametro_inventario"

    parametro_id: Mapped[int] = mapped_column(primary_key=True)
    umbral_general: Mapped[int] = mapped_column(Integer, nullable=False)
    # REF lógica al Usuario administrador (MS1) que fijó el parámetro.
    actualizado_por_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ParametroInventario parametro_id={self.parametro_id} umbral_general={self.umbral_general}>"
