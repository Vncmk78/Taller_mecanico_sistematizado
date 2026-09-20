"""Modelo Cliente (MS2: Vehículos, órdenes y capacidad).

MER (recuadro "BD MS2"): CLIENTE(cliente_id PK, usuario_id UK/REF → MS1, telefono?).

Cadena de relaciones Cliente–Usuario–Vehículo (INT-14, Semana 2):

    Usuario (MS1)  ──1:1 lógica──▶  Cliente (MS2)  ──1:N física──▶  Vehiculo (MS2)

- Usuario ↔ Cliente es una relación 1:1 LÓGICA que cruza de base (MS1 ↔ MS2).
  No se modela con `relationship()` ni con ForeignKey (§8: aislamiento de datos):
  se representa con la columna `usuario_id` marcada como única (un usuario tiene
  a lo más un perfil de cliente) y su integridad se resuelve por contrato de API
  contra MS1, no por la base de datos.
- Cliente ↔ Vehiculo es una relación 1:N FÍSICA dentro de la MISMA base (MS2),
  por lo que sí se navega con `relationship()` en ambos extremos (`back_populates`).
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

    # Lado "uno" de la relación 1:N con Vehiculo (misma base, MS2).
    #   - cascade="all, delete-orphan": al borrar un cliente se borran sus
    #     vehículos, y un vehículo desasociado de su cliente se elimina.
    #   - passive_deletes=True: deja que el borrado en cascada lo resuelva la BD
    #     mediante el ON DELETE CASCADE de la FK (definido en vehiculo.py), en vez
    #     de que el ORM cargue y borre cada vehículo uno por uno.
    #   - lazy="selectin": al cargar clientes, sus vehículos se traen en una sola
    #     consulta adicional (evita el problema N+1 al listar clientes).
    vehiculos: Mapped[list["Vehiculo"]] = relationship(
        back_populates="cliente",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Cliente cliente_id={self.cliente_id} usuario_id={self.usuario_id}>"
