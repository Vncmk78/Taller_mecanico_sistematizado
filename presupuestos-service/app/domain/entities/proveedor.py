"""Entidad de dominio Proveedor. Objeto puro, sin dependencias de framework ni BD."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Proveedor:
    nombre: str
    contacto: str | None = None
    proveedor_id: int | None = None
