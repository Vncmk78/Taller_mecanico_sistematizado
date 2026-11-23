"""Verificación de salud del backend vía Gateway (local o desplegado).

Consulta, a través de la Gateway:
  1. /api/health                         proceso de la Gateway
  2. /api/health/servicios               base de datos de MS1..MS4 (en paralelo)
  3. /api/health/servicios/{servicio}    proceso, base y (MS4) almacenamiento

Imprime una tabla legible y sale con 0 si todo está OK, 1 si algo falla.
Sirve como smoke test previo/posterior al despliegue y como evidencia.

Uso (desde backend/):
    python scripts/verificar_salud.py
    python scripts/verificar_salud.py --base https://mi-gateway.ejemplo.cl
    python scripts/verificar_salud.py --json salidas-integracion/salud.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

SERVICIOS = ("ms1_auth", "ms2_taller", "ms3_presupuestos", "ms4_evidencias")
VERDE, ROJO, GRIS, FIN = "\033[32m", "\033[31m", "\033[90m", "\033[0m"


def consultar(cliente: httpx.Client, ruta: str) -> tuple[int | None, dict]:
    """(código HTTP, cuerpo JSON). Código None si no hubo conexión."""
    try:
        respuesta = cliente.get(ruta)
    except httpx.HTTPError as exc:
        return None, {"error": type(exc).__name__}
    try:
        return respuesta.status_code, respuesta.json()
    except ValueError:
        return respuesta.status_code, {}


def verificar(base: str, timeout: float = 10.0) -> dict:
    """Ejecuta todas las consultas y devuelve un reporte serializable."""
    reporte: dict = {
        "base": base,
        "comprobado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": [],
    }
    with httpx.Client(base_url=base.rstrip("/"), timeout=timeout) as cliente:
        codigo, cuerpo = consultar(cliente, "/api/health")
        reporte["checks"].append(
            {"nombre": "gateway", "ruta": "/api/health", "codigo": codigo,
             "ok": codigo == 200, "detalle": cuerpo.get("status", cuerpo.get("error", "-"))}
        )

        codigo, cuerpo = consultar(cliente, "/api/health/servicios")
        reporte["checks"].append(
            {"nombre": "servicios (bases)", "ruta": "/api/health/servicios", "codigo": codigo,
             "ok": codigo == 200, "detalle": cuerpo.get("status", cuerpo.get("error", "-"))}
        )

        for servicio in SERVICIOS:
            ruta = f"/api/health/servicios/{servicio}"
            codigo, cuerpo = consultar(cliente, ruta)
            comprobaciones = cuerpo.get("comprobaciones", {})
            detalle = ", ".join(
                f"{nombre}={c.get('estado')}"
                + (f" ({c['latencia_ms']} ms)" if "latencia_ms" in c else "")
                for nombre, c in comprobaciones.items()
            ) or cuerpo.get("error", cuerpo.get("estado", "-"))
            reporte["checks"].append(
                {"nombre": servicio, "ruta": ruta, "codigo": codigo,
                 "ok": codigo == 200, "detalle": detalle}
            )
    reporte["ok"] = all(check["ok"] for check in reporte["checks"])
    return reporte


def imprimir(reporte: dict, color: bool = True) -> None:
    def pintar(texto: str, tono: str) -> str:
        return f"{tono}{texto}{FIN}" if color else texto

    print(f"\nSalud del backend SGTM — {reporte['base']}")
    print(pintar(f"Comprobado: {reporte['comprobado_en']}", GRIS))
    print("-" * 78)
    for check in reporte["checks"]:
        marca = pintar(" OK ", VERDE) if check["ok"] else pintar("FALLA", ROJO)
        codigo = check["codigo"] if check["codigo"] is not None else "sin conexión"
        print(f"[{marca}] {check['nombre']:<20} HTTP {codigo!s:<12} {check['detalle']}")
    print("-" * 78)
    total = len(reporte["checks"])
    buenos = sum(check["ok"] for check in reporte["checks"])
    resumen = f"{buenos}/{total} comprobaciones OK"
    print(pintar(resumen, VERDE if reporte["ok"] else ROJO) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8000", help="URL base de la Gateway")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout por consulta (s)")
    parser.add_argument("--json", type=Path, help="Guardar el reporte en este archivo JSON")
    parser.add_argument("--sin-color", action="store_true", help="Salida sin colores ANSI")
    args = parser.parse_args(argv)

    reporte = verificar(args.base, args.timeout)
    imprimir(reporte, color=not args.sin_color and sys.stdout.isatty())
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Reporte guardado en {args.json}")
    return 0 if reporte["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
