"""Modelo IngresoVehiculo (MS2: Vehículos, órdenes y capacidad).

MER (recuadro "BD MS2"):
  INGRESO_VEHICULO(ingreso_id PK, vehiculo_id FK, fecha_hora, salida_en?,
                   registrado_por_id REF → MS1).

Representa la ESTANCIA FÍSICA del vehículo en el taller (§4.1 y §4.7). Se crea
junto con la orden de trabajo porque `orden_trabajo.ingreso_id` es obligatorio:
toda orden nace de un ingreso. Una nueva orden reutiliza el ingreso abierto si el
vehículo no ha salido (no se descuenta de nuevo el cupo diario).

- `salida_en` registra la salida física; es independiente de que la orden
  termine (Entregado/Cancelado).
- `registrado_por_id` es una referencia LÓGICA al usuario de MS1 (sin FK, §8).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms2_taller.db import Base

if TYPE_CHECKING:
    from services.ms2_taller.models.vehiculo import Vehiculo


class IngresoVehiculo(Base):
    __tablename__ = "ingreso_vehiculo"

    __table_args__ = (
        CheckConstraint("registrado_por_id > 0", name="registrado_por_positivo"),
        # La salida no puede ser anterior a la entrada.
        CheckConstraint(
            "salida_en is null or salida_en >= fecha_hora",
            name="salida_posterior",
        ),
    )

    ingreso_id: Mapped[int] = mapped_column(primary_key=True)
    # RESTRICT: no se puede borrar un vehículo que tiene ingresos registrados;
    # la estancia física es historia del taller y se conserva.
    vehiculo_id: Mapped[int] = mapped_column(
        ForeignKey("vehiculo.vehiculo_id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    salida_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # REF lógica a Usuario (MS1). Sin ForeignKey a propósito (§8).
    registrado_por_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Many-to-one navegable. Sin back_populates en Vehiculo para no cambiar su
    # cascada con Cliente: si alguien intenta borrar un vehículo con ingresos,
    # la FK RESTRICT de la base lo impide.
    vehiculo: Mapped["Vehiculo"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IngresoVehiculo ingreso_id={self.ingreso_id} vehiculo_id={self.vehiculo_id}>"
