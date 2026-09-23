"""Modelos ORM del microservicio MS3: Presupuestos, Repuestos y Proveedores.

Se importan aquí TODOS los modelos del servicio para que `Base.metadata` (y por
lo tanto Alembic) los vea al generar y ejecutar las migraciones. Si un modelo no
aparece en este archivo, su tabla no entra en las migraciones.

Semana 3: Presupuesto, VersionPresupuesto, ItemPresupuesto, Proveedor, Repuesto,
MovimientoInventario y ParametroInventario.
Referencia: lámina 04-mer-erd, recuadro "BD MS3".
"""
from __future__ import annotations

from services.ms3_presupuestos.db import Base
from services.ms3_presupuestos.models.proveedor import Proveedor, Repuesto
from services.ms3_presupuestos.models.inventario import (
    MovimientoInventario,
    ParametroInventario,
)
from services.ms3_presupuestos.models.presupuesto import (
    ItemPresupuesto,
    Presupuesto,
    VersionPresupuesto,
)

__all__ = [
    "Base",
    "Proveedor",
    "Repuesto",
    "MovimientoInventario",
    "ParametroInventario",
    "Presupuesto",
    "VersionPresupuesto",
    "ItemPresupuesto",
]
