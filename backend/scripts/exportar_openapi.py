"""Exporta el contrato OpenAPI de la Gateway a un archivo versionado.

La Gateway construye su `/openapi.json` en memoria (`gateway/openapi.py`). Este
script lo congela en `docs/openapi/sgtm-gateway-<version>.json`, que es la copia
estable que consumen el frontend web y la app móvil (Integración IV) sin tener
que levantar la Gateway: sirve para generar clientes, tipos y mocks.

No necesita servicios levantados ni base de datos.

Uso, desde backend/:
    python scripts/exportar_openapi.py              # escribe el archivo
    python scripts/exportar_openapi.py --verificar  # 0 si está al día, 1 si no

Si cambias el contrato publicado, sube `_VERSION` en `gateway/openapi.py`
según `docs/versionado-contrato-openapi.md` y vuelve a exportar: el archivo de
la versión anterior se conserva como historial.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

from gateway.main import app  # noqa: E402  (requiere backend/ en el path)

DIRECTORIO_CONTRATOS = RAIZ_BACKEND / "docs" / "openapi"


def construir_documento() -> dict:
    """OpenAPI recién construido (sin el que la app tenga en caché)."""
    app.openapi_schema = None
    try:
        return app.openapi()
    finally:
        app.openapi_schema = None


def serializar(documento: dict) -> str:
    """Formato canónico: claves en el orden de origen, UTF-8 y salto final."""
    return json.dumps(documento, ensure_ascii=False, indent=2) + "\n"


def ruta_contrato(version: str) -> Path:
    return DIRECTORIO_CONTRATOS / f"sgtm-gateway-{version}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--verificar",
        action="store_true",
        help="no escribe; falla si el archivo de la versión actual no coincide",
    )
    args = parser.parse_args()

    documento = construir_documento()
    version = documento["info"]["version"]
    destino = ruta_contrato(version)
    contenido = serializar(documento)

    if args.verificar:
        if not destino.exists():
            print(f"Falta {destino.relative_to(RAIZ_BACKEND)}: ejecuta el script sin --verificar")
            return 1
        if destino.read_text(encoding="utf-8") != contenido:
            print(
                f"{destino.relative_to(RAIZ_BACKEND)} no coincide con el contrato "
                f"publicado. Si el cambio es intencional, sube la versión y exporta."
            )
            return 1
        print(f"OK: {destino.relative_to(RAIZ_BACKEND)} está al día (versión {version})")
        return 0

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8", newline="\n")
    print(f"Escrito {destino.relative_to(RAIZ_BACKEND)} (versión {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
