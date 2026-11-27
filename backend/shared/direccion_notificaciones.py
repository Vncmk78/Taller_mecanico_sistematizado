"""Direcciones locales y cabeceras de las notificaciones entre microservicios.

En Kubero las URLs se definen con ``MS1_MS2_URL`` / ``MS3_MS1_URL``. Este módulo
aporta el valor de desarrollo local y la cabecera de servicio compartida.
"""
from __future__ import annotations

from typing import Literal


def url_notificaciones_por_defecto(ms: Literal[1, 2]) -> str:
    """Valor usado cuando no se configura la URL interna del servicio."""
    return f"http://localhost:800{ms}"


def cabeceras_notificaciones(
    url_base: str, ms: Literal[1, 2], secreto_servicio: str
) -> dict[str, str]:
    """Cabecera de autenticación entre servicios, sin secretos de plataforma."""
    return {"X-Service-Token": secreto_servicio}
