"""Ruta HTTP a MS3 cuando Vercel no permite bindings en ambos sentidos."""
from __future__ import annotations

import os
import re


def _origen_despliegue() -> str | None:
    if os.environ.get("VERCEL") != "1":
        return None
    host = os.environ.get("VERCEL_URL", "").strip()
    # VERCEL_URL es un dominio sin protocolo, ruta, puerto ni credenciales.
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", host):
        return None
    if any(not etiqueta or etiqueta.startswith("-") or etiqueta.endswith("-")
           for etiqueta in host.split(".")):
        return None
    return f"https://{host.lower()}"


def url_ms3_por_defecto() -> str:
    if os.environ.get("VERCEL") != "1":
        return "http://localhost:8003"
    origen = _origen_despliegue()
    if origen is None:
        raise ValueError("Habilite VERCEL_URL o configure MS2_MS3_URL explícitamente")
    # La URL de ESTE despliegue evita que un preview consulte otra versión.
    return f"{origen}/ms3"


def cabeceras_para_ms3(url_base: str, token: str) -> dict[str, str]:
    cabeceras = {"Authorization": f"Bearer {token}"}
    origen = _origen_despliegue()
    secreto = os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET", "")
    # El secreto de plataforma nunca se envía a otro host, alias o servicio.
    if origen and url_base.rstrip("/") == f"{origen}/ms3" and secreto:
        cabeceras["x-vercel-protection-bypass"] = secreto
    return cabeceras
