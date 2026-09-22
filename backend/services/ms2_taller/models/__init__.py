"""Modelos ORM del microservicio MS2: Vehículos y Órdenes de Trabajo.

Se importan aquí TODOS los modelos del servicio para que `Base.metadata` (y por
lo tanto Alembic) los vea al generar y ejecutar las migraciones. Si un modelo no
aparece en este archivo, su tabla no entra en las migraciones.

Modelos iniciales (INT-13, Semana 1): Cliente, Vehiculo.
Referencia: lámina 04-mer-erd, recuadro "BD MS2 | Vehículos, órdenes y capacidad".
"""
from __future__ import annotations

from services.ms2_taller.db import Base
from services.ms2_taller.models.cliente import Cliente
from services.ms2_taller.models.vehiculo import Vehiculo

__all__ = ["Base", "Cliente", "Vehiculo"]
