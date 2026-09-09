"""Modelo Vehículo.

MER: VEHICULO(id, cliente_id FK, patente UK, marca, modelo, anio, kilometraje).
La patente es única (restricción del negocio pedida para Semana 1/2).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.cliente import Cliente


class Vehiculo(Base):
    __tablename__ = "vehiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("cliente.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    patente: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    marca: Mapped[str] = mapped_column(String(60), nullable=False)
    modelo: Mapped[str] = mapped_column(String(60), nullable=False)
    anio: Mapped[int | None] = mapped_column(Integer)
    kilometraje: Mapped[int | None] = mapped_column(Integer)

    cliente: Mapped["Cliente"] = relationship(back_populates="vehiculos")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vehiculo id={self.id} patente={self.patente!r}>"
