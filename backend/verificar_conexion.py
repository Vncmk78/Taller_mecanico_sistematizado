"""Comprueba que los cuatro servicios pueden conectarse a SU base.

Uso:  python verificar_conexion.py
Devuelve código 0 si las cuatro conexiones responden; 1 si alguna falla.
"""
from __future__ import annotations

import sys

from sqlalchemy import text

SERVICIOS = ["ms1_auth", "ms2_taller", "ms3_presupuestos", "ms4_evidencias"]


def main() -> int:
    fallos = 0
    for paquete in SERVICIOS:
        modulo = __import__(f"services.{paquete}.db", fromlist=["engine"])
        cfg = __import__(f"services.{paquete}.config", fromlist=["settings"])
        nombre = cfg.settings.SERVICE_NAME
        try:
            with modulo.engine.connect() as conexion:
                version = conexion.execute(text("SHOW server_version")).scalar_one()
            print(f"[OK]    {nombre}  ->  PostgreSQL {version}")
        except Exception as error:  # noqa: BLE001
            fallos += 1
            print(f"[FALLA] {nombre}  ->  {type(error).__name__}: {error}")
    if fallos:
        print(f"\n{fallos} de {len(SERVICIOS)} conexiones fallaron.")
        print("Revisa que los contenedores esten arriba (docker compose ps) "
              "y que el archivo .env tenga las cuatro URLs.")
        return 1
    print("\nLas cuatro conexiones responden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
