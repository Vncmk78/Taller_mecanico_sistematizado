"""Entidad de dominio ParametroInventario (umbral general vigente)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ParametroInventario:
    umbral_general: int
    actualizado_por_id: int | None = None
    vigente_desde: datetime | None = None
    vigente_hasta: datetime | None = None
    parametro_id: int | None = None
