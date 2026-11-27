"""Dirección local por defecto y cabeceras de las consultas MS2 → MS3.

En Kubero la URL se define explícitamente con ``MS2_MS3_URL``. Este módulo solo
aporta el valor de desarrollo local y las cabeceras internas, sin depender de
variables de una plataforma de despliegue retirada.
"""
from __future__ import annotations

from shared.correlacion import cabeceras_correlacion


def url_ms3_por_defecto() -> str:
    """Valor usado sólo cuando no se configura ``MS2_MS3_URL``."""
    return "http://localhost:8003"


def cabeceras_para_ms3(url_base: str, token: str) -> dict[str, str]:
    """Propaga el JWT del usuario y el identificador de correlación."""
    return {"Authorization": f"Bearer {token}", **cabeceras_correlacion()}
