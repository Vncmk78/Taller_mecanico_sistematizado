"""Modelo HistorialUmbral (MS3: Presupuestos, repuestos y proveedores).

MER (recuadro "BD MS3"):
  HISTORIAL_UMBRAL(historial_id PK, repuesto_id? FK (vacío = umbral general),
                   valor_anterior?, valor_nuevo?,
                   administrador_id REF → MS1, fecha_hora)

Auditoría de cambios de umbral de stock (Semana 3, §4.6). Cada cambio del
umbral general o de un umbral particular deja una fila con el valor anterior,
el nuevo, el administrador responsable, la fecha/hora y una observación.

Reglas (nota del MER):
- repuesto_id vacío  → cambio del umbral GENERAL: valor_nuevo obligatorio.
- repuesto_id con valor → umbral PARTICULAR: valor_nuevo vacío significa
  "se retiró el umbral particular y el repuesto vuelve a usar el general".
- Los umbrales nunca son negativos.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from services.ms3_presupuestos.db import Base


class HistorialUmbral(Base):
    __tablename__ = "historial_umbral"

    __table_args__ = (
        CheckConstraint(
            "repuesto_id is not null or valor_nuevo is not null",
            name="general_requiere_valor",
        ),
        CheckConstraint(
            "(valor_anterior is null or valor_anterior >= 0) "
            "and (valor_nuevo is null or valor_nuevo >= 0)",
            name="valores_no_negativos",
        ),
        CheckConstraint(
            "valor_anterior is distinct from valor_nuevo",
            name="cambio_real",
        ),
        CheckConstraint("administrador_id > 0", name="administrador_positivo"),
        CheckConstraint(
            "observacion is null or btrim(observacion) <> ''",
            name="observacion_no_vacia",
        ),
    )

    historial_id: Mapped[int] = mapped_column(primary_key=True)
    # Vacío = cambio del umbral general.
    repuesto_id: Mapped[int | None] = mapped_column(
        ForeignKey("repuesto.repuesto_id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    valor_anterior: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valor_nuevo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # REF lógica a Usuario (MS1). Sin ForeignKey a propósito (§8).
    administrador_id: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        destino = self.repuesto_id or "general"
        return f"<HistorialUmbral {destino}: {self.valor_anterior}->{self.valor_nuevo}>"
