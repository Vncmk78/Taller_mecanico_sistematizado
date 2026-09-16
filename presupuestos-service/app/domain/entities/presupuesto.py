"""Entidad de dominio Presupuesto (cabecera)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Presupuesto:
    # REF lógica a la Orden de Trabajo (MS2); un presupuesto por orden.
    orden_id: int
    presupuesto_id: int | None = None
    creado_en: datetime | None = None
