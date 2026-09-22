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

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from services.ms2_taller.db import Base

if TYPE_CHECKING:
    from services.ms2_taller.models.cliente import Cliente


class Vehiculo(Base):
    __tablename__ = "vehiculo"

    # Restricciones e índices a nivel de BD (INT-15, Semana 2). Son la fuente de
    # verdad junto con la migración 0002_ms2:
    #   - uq_vehiculo_patente: índice ÚNICO FUNCIONAL sobre upper(patente) →
    #     patente única insensible a mayúsculas ("abcd12" == "ABCD12").
    #   - ck_vehiculo_patente_formato: largo razonable y ya normalizada (mayúsculas,
    #     sin espacios sobrantes); el normalizado lo garantiza también @validates.
    #   - ck_vehiculo_anio_valido / ck_vehiculo_km_no_negativo: rangos coherentes.
    __table_args__ = (
        Index("uq_vehiculo_patente", text("upper(patente)"), unique=True),
        # El nombre va sin el prefijo "ck_vehiculo_": la convención de nombres
        # (shared/db.py) lo antepone → ck_vehiculo_patente_formato, etc.
        CheckConstraint(
            "char_length(btrim(patente)) between 5 and 10 "
            "and patente = upper(btrim(patente))",
            name="patente_formato",
        ),
        CheckConstraint(
            "anio is null or (anio between 1900 and 2100)",
            name="anio_valido",
        ),
        CheckConstraint(
            "kilometraje is null or kilometraje >= 0",
            name="km_no_negativo",
        ),
    )

    vehiculo_id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("cliente.cliente_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # La unicidad NO va aquí como unique=True: se implementa como índice único
    # funcional case-insensitive en __table_args__ (ver arriba).
    patente: Mapped[str] = mapped_column(String(10), nullable=False)
    marca: Mapped[str] = mapped_column(String(60), nullable=False)
    modelo: Mapped[str] = mapped_column(String(60), nullable=False)
    anio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kilometraje: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Lado "uno" navegable de la relación: vehiculo.cliente ↔ cliente.vehiculos.
    cliente: Mapped["Cliente"] = relationship(back_populates="vehiculos")

    @validates("patente")
    def _normalizar_patente(self, _key: str, valor: str | None) -> str | None:
        """Normaliza la patente antes de guardarla: sin espacios y en mayúsculas.

        Deja los datos coherentes con el índice único funcional sobre upper(patente)
        y con el CHECK ck_vehiculo_patente_formato, de modo que la unicidad
        insensible a mayúsculas se cumpla siempre desde la aplicación.
        """
        if valor is None:
            return valor
        return valor.strip().upper()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vehiculo vehiculo_id={self.vehiculo_id} patente={self.patente!r}>"
