"""Modelo Vehiculo (MS2: Vehículos, órdenes y capacidad).

MER (recuadro "BD MS2"):
  VEHICULO(vehiculo_id PK, cliente_id FK, patente UK, marca, modelo, anio,
           kilometraje).

Lado "muchos" de la relación 1:N con Cliente (INT-14, Semana 2): un cliente
tiene varios vehículos, un vehículo pertenece a un solo cliente.

`cliente_id` sí es una ForeignKey física: Cliente vive en la MISMA base (MS2).
Su `ON DELETE CASCADE` es lo que permite que el borrado en cascada del cliente
lo resuelva la propia base (ver `passive_deletes=True` en Cliente.vehiculos).

La patente es única (UK) — un vehículo no puede estar registrado dos veces. El
detalle de restricciones, índices y la validación fina de la patente única se
completan en INT-15 (Semana 2); aquí queda ya modelada la unicidad base.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms2_taller.db import Base

if TYPE_CHECKING:
    from services.ms2_taller.models.cliente import Cliente


class Vehiculo(Base):
    __tablename__ = "vehiculo"

    vehiculo_id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("cliente.cliente_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    patente: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    marca: Mapped[str] = mapped_column(String(60), nullable=False)
    modelo: Mapped[str] = mapped_column(String(60), nullable=False)
    anio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kilometraje: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Lado "uno" navegable de la relación: vehiculo.cliente ↔ cliente.vehiculos.
    cliente: Mapped["Cliente"] = relationship(back_populates="vehiculos")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vehiculo vehiculo_id={self.vehiculo_id} patente={self.patente!r}>"
