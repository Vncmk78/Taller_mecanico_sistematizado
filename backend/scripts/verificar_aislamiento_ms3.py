"""Verifica que la base de datos de MS3 esté aislada de los demás servicios.

Revisa, sin modificar nada:
1. El modelo ORM: FKs solo entre tablas de MS3, referencias lógicas sin FK,
   ninguna tabla compartida con MS1, MS2 o MS4.
2. La configuración: MS3_DATABASE_URL no apunta a la misma base que otro servicio.
3. La base real: solo tablas de MS3 (+ alembic_version), ninguna FK hacia
   fuera, sin dblink/postgres_fdw ni tablas foráneas.

Uso (desde backend/, con .env configurado; sirve para local o Neon):
    python scripts/verificar_aislamiento_ms3.py
Termina con código 1 si encuentra problemas.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ms3_presupuestos import aislamiento  # noqa: E402
from services.ms3_presupuestos import models  # noqa: E402,F401
from services.ms3_presupuestos.db import Base, engine  # noqa: E402


def _urls_de_otros_servicios() -> dict[str, str]:
    # Se leen como texto: no hace falta configurar los otros servicios completos.
    entorno = {**dotenv_values(".env"), **os.environ}
    return {s: entorno.get(f"{s}_DATABASE_URL") or ""
            for s in ("MS1", "MS2", "MS4")}


def main() -> int:
    secciones = {
        "Modelo ORM": aislamiento.problemas_de_metadata(Base.metadata),
        "Configuración": aislamiento.problemas_de_urls(
            engine.url.render_as_string(hide_password=True), _urls_de_otros_servicios()),
    }
    with engine.connect() as conexion:
        secciones[f"Base {engine.url.database}"] = aislamiento.problemas_en_base(
            conexion, Base.metadata)

    total = 0
    for titulo, problemas in secciones.items():
        print(f"[{'OK' if not problemas else 'FALLA'}] {titulo}")
        for problema in problemas:
            print(f"    - {problema}")
        total += len(problemas)
    print("MS3 aislado." if total == 0 else f"{total} problema(s) de aislamiento.")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
