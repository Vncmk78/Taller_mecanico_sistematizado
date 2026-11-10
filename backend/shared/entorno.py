"""Archivo de entorno que leen los servicios y los scripts.

Por defecto es `.env` (comportamiento histórico). El ambiente de pruebas
separado exporta `SGTM_ENV_FILE=.env.pruebas` para que ningún proceso vuelva a
leer el `.env` del ambiente local existente; además, `scripts/ambiente_pruebas.py`
exporta cada variable al proceso, que tiene prioridad sobre cualquier archivo.
"""
from __future__ import annotations

import os
from pathlib import Path

VARIABLE_ARCHIVO_ENTORNO = "SGTM_ENV_FILE"


def archivo_entorno() -> str:
    """Nombre (o ruta) del archivo de entorno elegido para este proceso."""

    return os.environ.get(VARIABLE_ARCHIVO_ENTORNO) or ".env"


def ruta_entorno(base: Path) -> Path:
    """Ruta del archivo de entorno, relativa a `base` si no es absoluta."""

    ruta = Path(archivo_entorno())
    return ruta if ruta.is_absolute() else base / ruta
