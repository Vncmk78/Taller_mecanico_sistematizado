"""Entidad de dominio Repuesto."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Repuesto:
    nombre: str
    proveedor_id: int
    stock: int = 0
    # Umbral propio; si es None se usa el umbral general del inventario (§4.6).
    umbral_particular: int | None = None
    repuesto_id: int | None = None
