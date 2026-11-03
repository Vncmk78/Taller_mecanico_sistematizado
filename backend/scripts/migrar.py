"""Aplica heads en las cuatro bases explícitamente configuradas y verifica el resultado.

Uso: python scripts/migrar.py. Modifica las bases indicadas en backend/.env o
en las variables del proceso. No ejecutarlo contra producción sin autorización.
No crea bases, no ejecuta seeds, no hace stamp ni downgrade.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verificar_migraciones import (
    BACKEND_DIR, SERVICIOS, configuracion, mostrar, verificar_todas,
)


def main() -> int:
    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))
    print("Preverificación de las cuatro bases (checkout actual):")
    previas = verificar_todas()
    if mostrar(previas) == 2:
        print("No se aplicaron migraciones: resolver errores o revisiones incompatibles.")
        return 2

    for servicio in SERVICIOS:
        print(f"Migrando {servicio} a heads...", flush=True)
        try:
            config = configuracion(servicio)
            command.upgrade(config, "heads")
            command.current(config, verbose=True)
        except Exception as exc:
            print(f"Fallo en {servicio} ({type(exc).__name__}).")
            print("Los servicios anteriores pueden haber migrado; revisar antes de reintentar.")
            return 2

    print("Verificación final:")
    codigo = mostrar(verificar_todas())
    if codigo == 0:
        print("Las cuatro bases coinciden con los heads de este checkout.")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
