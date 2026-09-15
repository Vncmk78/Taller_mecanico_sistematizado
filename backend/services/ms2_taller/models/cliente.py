"""Modelo Cliente (MS2: Vehículos, órdenes y capacidad).

MER (recuadro "BD MS2"): CLIENTE(cliente_id PK, usuario_id UK/REF → MS1, telefono?).

`usuario_id` es una REFERENCIA LÓGICA al Usuario que vive en la base de MS1
(§8: aislamiento de datos). Por eso NO se declara como ForeignKey: no existen
claves foráneas físicas entre bases de servicios distintos. Se guarda como un
entero suelto y único (un usuario corresponde a un solo perfil de cliente); la
existencia real de ese usuario se valida por contrato de API contra MS1.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms2_taller.db import Base

if TYPE_CHECKING:
    from services.ms2_taller.models.vehiculo import Vehiculo


class Cliente(Base):
    __tablename__ = "cliente"

    cliente_id: Mapped[int] = mapped_column(primary_key=True)
    # REF lógica a Usuario (MS1). Único: 1 usuario ↔ 1 perfil de cliente.
    # Sin ForeignKey a propósito (§8): la referencia cruza de base.
    usuario_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)

    vehiculos: Mapped[list["Vehiculo"]] = relationship(
        back_populates="cliente",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Cliente cliente_id={self.cliente_id} usuario_id={self.usuario_id}>"
