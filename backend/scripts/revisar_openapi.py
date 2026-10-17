"""Revisión del OpenAPI de la Gateway contra el de los microservicios (Semana 4).

La Gateway publica en /openapi.json los contratos de /api/auth/* (MS1) y de
/api/vehiculos y /api/ordenes (MS2), escritos a mano en gateway/contratos. Si
un microservicio cambia su API y la Gateway no, el frontend trabaja con un
contrato falso. Este script lo detecta comparando, con los servicios LEVANTADOS:

1. que cada ruta y método documentados en la Gateway existan en el microservicio;
2. que los campos del body de entrada y de la respuesta exitosa coincidan.

Uso, desde backend/ (Gateway en :8000, MS1 en :8001, MS2 en :8002):
    python scripts/revisar_openapi.py

Sale con código 0 si no hay discrepancias y 1 si las hay.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gateway.rutas import RUTAS  # noqa: E402  (requiere backend/ en el path)

# URL base local de cada microservicio (misma tabla que el README).
BASES_LOCALES = {
    "http://localhost:8001": "MS1",
    "http://localhost:8002": "MS2",
    "http://localhost:8003": "MS3",
    "http://localhost:8004": "MS4",
}
METODOS = {"get", "post", "put", "patch", "delete"}


def descargar(url: str) -> dict | None:
    try:
        return httpx.get(f"{url}/openapi.json", timeout=10).json()
    except (httpx.HTTPError, ValueError):
        return None


def resolver(esquema: dict | None, spec: dict) -> dict:
    """Sigue $ref, allOf y arrays hasta llegar al objeto con `properties`."""
    esquema = esquema or {}
    for _ in range(10):
        if "$ref" in esquema:
            nombre = esquema["$ref"].rsplit("/", 1)[-1]
            esquema = spec.get("components", {}).get("schemas", {}).get(nombre, {})
        elif esquema.get("type") == "array":
            esquema = esquema.get("items", {})
        elif "allOf" in esquema and len(esquema["allOf"]) == 1:
            esquema = esquema["allOf"][0]
        else:
            break
    return esquema


def campos(esquema: dict | None, spec: dict) -> set[str]:
    return set(resolver(esquema, spec).get("properties", {}))


def campos_body(op: dict, spec: dict) -> set[str]:
    contenido = op.get("requestBody", {}).get("content", {})
    return campos(contenido.get("application/json", {}).get("schema"), spec)


def campos_exito(op: dict, spec: dict) -> set[str]:
    for codigo in ("200", "201"):
        contenido = op.get("responses", {}).get(codigo, {}).get("content", {})
        if contenido:
            return campos(contenido.get("application/json", {}).get("schema"), spec)
    return set()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway", default="http://localhost:8000")
    gw = parser.parse_args().gateway.rstrip("/")

    spec_gw = descargar(gw)
    if spec_gw is None:
        print(f"No se pudo leer {gw}/openapi.json: ¿la Gateway está levantada?")
        return 1

    specs: dict[str, dict | None] = {}
    discrepancias: list[str] = []
    revisadas = 0

    for ruta, operaciones in sorted(spec_gw.get("paths", {}).items()):
        if not ruta.startswith("/api/"):
            continue
        ruta_ms = ruta[len("/api"):]
        prefijo = ruta_ms.strip("/").split("/", 1)[0]
        base = RUTAS.get(prefijo)
        if base is None:
            continue  # ruta propia de la Gateway (p. ej. /api/health)
        nombre_ms = BASES_LOCALES.get(base or "", base or "?")
        if base not in specs:
            specs[base] = descargar(base) if base else None
        spec_ms = specs[base]
        if spec_ms is None:
            discrepancias.append(f"{ruta}: no se pudo leer el OpenAPI de {nombre_ms}")
            continue

        for metodo, op_gw in operaciones.items():
            if metodo not in METODOS:
                continue
            revisadas += 1
            etiqueta = f"{metodo.upper()} {ruta} → {nombre_ms} {ruta_ms}"
            op_ms = spec_ms.get("paths", {}).get(ruta_ms, {}).get(metodo)
            if op_ms is None:
                discrepancias.append(f"{etiqueta}: la ruta NO existe en {nombre_ms}")
                continue
            for tipo, f in (("body", campos_body), ("respuesta", campos_exito)):
                en_gw, en_ms = f(op_gw, spec_gw), f(op_ms, spec_ms)
                if en_gw != en_ms:
                    discrepancias.append(
                        f"{etiqueta}: campos de {tipo} distintos — "
                        f"solo en Gateway {sorted(en_gw - en_ms)}, "
                        f"solo en {nombre_ms} {sorted(en_ms - en_gw)}"
                    )

    print(f"Operaciones revisadas: {revisadas}")
    if not discrepancias:
        print("Sin discrepancias entre el OpenAPI de la Gateway y los microservicios.")
        return 0
    print(f"Discrepancias encontradas ({len(discrepancias)}):")
    for d in discrepancias:
        print(f"  - {d}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
