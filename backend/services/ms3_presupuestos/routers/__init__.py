"""Routers HTTP del microservicio MS3 (Presupuestos, Repuestos y Proveedores).

Cada recurso tendrá su propio módulo y su APIRouter, y se agregará a `ROUTERS`
para que `main.py` lo registre sin tocar nada más:

    presupuestos.py  →  /presupuestos   (versiones, ítems, envío y decisión)
    repuestos.py     →  /repuestos      (catálogo, stock y umbral particular)
    proveedores.py   →  /proveedores
    inventario.py    →  /inventario     (movimientos y umbral general)

Las rutas coinciden con los prefijos que la Gateway ya envía a MS3
(gateway/rutas.py). Los endpoints se implementan en la tarea de Semana 5
"Implementar persistencia ORM y endpoints iniciales de presupuestos" y en
"Implementar persistencia y endpoints de repuestos y proveedores".

Capas: router (HTTP) → services (reglas y transacción) → models (ORM).
Un router nunca abre sesiones ni escribe SQL: recibe `db` por `get_db` y
delega en services.
"""
from __future__ import annotations

from fastapi import APIRouter

ROUTERS: list[APIRouter] = []

__all__ = ["ROUTERS"]
