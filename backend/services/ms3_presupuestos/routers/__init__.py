"""Routers HTTP del microservicio MS3 (Presupuestos, Repuestos y Proveedores).

Cada recurso tendrá su propio módulo y su APIRouter, y se agregará a `ROUTERS`
para que `main.py` lo registre sin tocar nada más:

    presupuestos.py  →  /presupuestos   (versiones, ítems, envío y decisión)
    repuestos.py     →  /repuestos      (catálogo, stock y umbral particular)
    proveedores.py   →  /proveedores
    inventario.py    →  /inventario     (movimientos y umbral general)

Las rutas coinciden con los prefijos que la Gateway ya envía a MS3
(gateway/rutas.py). Implementado: presupuestos.py, repuestos.py y
proveedores.py (Semana 5). Pendiente: inventario (movimientos y umbral general).

Capas: router (HTTP) → services (reglas y transacción) → models (ORM).
Un router nunca abre sesiones ni escribe SQL: recibe `db` por `get_db` y
delega en services.
"""
from __future__ import annotations

from fastapi import APIRouter

from services.ms3_presupuestos.routers.presupuestos import router as router_presupuestos
from services.ms3_presupuestos.routers.proveedores import router as router_proveedores
from services.ms3_presupuestos.routers.repuestos import router as router_repuestos

ROUTERS: list[APIRouter] = [router_presupuestos, router_repuestos, router_proveedores]

__all__ = ["ROUTERS"]
