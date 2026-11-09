"""Rutas internas de notificaciones sin bindings cíclicos de Vercel."""

import os
import re
from typing import Literal


def _origen_despliegue() -> str | None:
    if os.environ.get("VERCEL") != "1":
        return None
    host = os.environ.get("VERCEL_URL", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", host):
        return None
    if any(not p or p.startswith("-") or p.endswith("-") for p in host.split(".")):
        return None
    return f"https://{host.lower()}"


def url_notificaciones_por_defecto(ms: Literal[1, 2]) -> str:
    if os.environ.get("VERCEL") != "1":
        return f"http://localhost:800{ms}"
    origen = _origen_despliegue()
    if origen is None:
        raise ValueError("Configure VERCEL_URL válida o una URL interna explícita")
    return f"{origen}/ms{ms}"


def cabeceras_notificaciones(
    url_base: str, ms: Literal[1, 2], secreto_servicio: str
) -> dict[str, str]:
    h = {"X-Service-Token": secreto_servicio}
    origen = _origen_despliegue()
    bypass = os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET", "")
    if origen and url_base.rstrip("/") == f"{origen}/ms{ms}" and bypass:
        h["x-vercel-protection-bypass"] = bypass
    return h
