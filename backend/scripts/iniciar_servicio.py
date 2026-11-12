"""Arranque del contenedor: SGTM_SERVICIO=gateway|ms1|ms2|ms3|ms4|migraciones, PORT=8000.

`migraciones` no levanta un servidor: ejecuta scripts/inicializar_bd.py (espera
las bases, migra MS1 → MS4 en orden, verifica) y termina con su código de salida.
Sirve como tarea previa al despliegue (job de Kubero o `docker compose run`).
"""
from __future__ import annotations

import os
import sys

MODULOS = {
    "gateway": "gateway.main:app",
    "ms1": "services.ms1_auth.main:app",
    "ms2": "services.ms2_taller.main:app",
    "ms3": "services.ms3_presupuestos.main:app",
    "ms4": "services.ms4_evidencias.main:app",
}


def comando(entorno: dict[str, str]) -> list[str]:
    servicio = entorno.get("SGTM_SERVICIO", "gateway")
    if servicio == "migraciones":
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inicializar_bd.py")
        return [sys.executable, script]
    if servicio not in MODULOS:
        raise ValueError("SGTM_SERVICIO debe ser gateway, ms1, ms2, ms3, ms4 o migraciones")
    try:
        puerto = int(entorno.get("PORT", "8000"))
    except ValueError:
        raise ValueError("PORT debe ser un número entre 1 y 65535") from None
    if not 1 <= puerto <= 65535:
        raise ValueError("PORT debe ser un número entre 1 y 65535")
    return [sys.executable, "-m", "uvicorn", MODULOS[servicio], "--host", "0.0.0.0", "--port", str(puerto)]


def main() -> int:
    try:
        argumentos = comando(dict(os.environ))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    # Reemplaza el proceso para que Kubernetes pueda enviar SIGTERM a Uvicorn.
    os.execv(sys.executable, argumentos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
