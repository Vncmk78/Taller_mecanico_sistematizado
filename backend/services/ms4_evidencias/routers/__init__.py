"""Routers de HTTP del microservicio MS4 (Evidencia Multimedia).

Cada recurso tiene su propio módulo y su APIRouter, y se agrega a `ROUTERS`
para que `main.py` lo registre sin tocar nada más:

    evidencias.py  →  /evidencias   (subida, listado, detalle y descarga)

Las rutas coinciden con los prefijos que la Gateway ya envía a MS4
(gateway/rutas.py). Implementado: evidencias.py (Semana 5).

Capas: router (HTTP) → services (reglas y transacción) → models (ORM).
Un router nunca abre sesiones ni escribe SQL: recibe `db` por `get_db` y
delega en services.
"""
from __future__ import annotations

from fastapi import APIRouter

from services.ms4_evidencias.routers.evidencias import router as router_evidencias

ROUTERS: list[APIRouter] = [router_evidencias]

__all__ = ["ROUTERS"]
