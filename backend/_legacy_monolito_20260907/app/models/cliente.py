"""Modelo Cliente.

MER: CLIENTE(id, usuario_id FK, telefono). Relación 1:1 con Usuario y 1:N con
Vehículo ("posee").
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.usuario import Usuario
    from app.models.vehiculo import Vehiculo


class Cliente(Base):
    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique=True refuerza el 1:1 con Usuario.
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    telefono: Mapped[str | None] = mapped_column(String(30))

    usuario: Mapped["Usuario"] = relationship(back_populates="cliente")
    vehiculos: Mapped[list["Vehiculo"]] = relationship(
        back_populates="cliente",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Cliente id={self.id} usuario_id={self.usuario_id}>"
