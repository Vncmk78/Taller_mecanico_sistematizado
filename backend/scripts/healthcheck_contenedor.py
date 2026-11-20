"""HEALTHCHECK del contenedor backend (Gateway o microservicio).

Docker lo ejecuta dentro del contenedor cada cierto intervalo. Lee las mismas
variables que `iniciar_servicio.py` (SGTM_SERVICIO y PORT) y consulta el
endpoint de vida del proceso que corresponde:

    gateway        -> GET /api/health
    ms1..ms4       -> GET /health
    migraciones    -> no levanta servidor: siempre sano (sale con 0)

Sale con 0 si responde 200 y con 1 en cualquier otro caso. Usa solo la
biblioteca estándar porque la imagen python:slim no trae curl ni wget.
No consulta la base de datos: eso lo cubre `/health/db` y la Gateway en
`/api/health/servicios`; así un corte de la base no reinicia el contenedor.
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

RUTAS = {
    "gateway": "/api/health",
    "ms1": "/health",
    "ms2": "/health",
    "ms3": "/health",
    "ms4": "/health",
}
TIMEOUT_SEGUNDOS = 3.0


def url_salud(entorno: dict[str, str]) -> str | None:
    """URL local a consultar, o None si el servicio no expone HTTP (migraciones)."""
    servicio = entorno.get("SGTM_SERVICIO", "gateway")
    if servicio == "migraciones":
        return None
    if servicio not in RUTAS:
        raise ValueError("SGTM_SERVICIO debe ser gateway, ms1, ms2, ms3, ms4 o migraciones")
    puerto = entorno.get("PORT", "8000")
    if not puerto.isdigit() or not 1 <= int(puerto) <= 65535:
        raise ValueError("PORT debe ser un número entre 1 y 65535")
    return f"http://127.0.0.1:{puerto}{RUTAS[servicio]}"


def comprobar(url: str, timeout: float = TIMEOUT_SEGUNDOS) -> bool:
    """True solo si el endpoint responde 200 dentro del timeout."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as respuesta:  # noqa: S310 (URL local fija)
            return respuesta.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def main() -> int:
    try:
        url = url_salud(dict(os.environ))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if url is None:
        return 0
    if comprobar(url):
        return 0
    print(f"healthcheck: {url} no respondió 200", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
