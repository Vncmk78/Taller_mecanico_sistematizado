"""Registro de endpoints públicos y evidencia básica del despliegue (Semana 11).

Recorre los endpoints públicos de la web y de la Gateway y guarda, para cada
uno, el código HTTP, la latencia, el X-Request-ID y si llegó con HSTS. No usa
credenciales: las rutas protegidas deben responder 401 y eso también es
evidencia (la Gateway enruta y el microservicio valida el JWT).

Solo usa la biblioteca estándar.

Uso (desde backend/):
    python scripts/registrar_evidencia_despliegue.py
    python scripts/registrar_evidencia_despliegue.py --json ../docs/evidencia/despliegue.json
    python scripts/registrar_evidencia_despliegue.py --api http://127.0.0.1:8080 --web http://127.0.0.1:8081

Sale con 1 si algún endpoint no responde lo esperado.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api-tallerconnect.inf.uct.cl"
WEB = "https://tallerconnect.inf.uct.cl"

# (origen, método, ruta, código esperado, qué demuestra)
ENDPOINTS = (
    ("api", "GET", "/", 200, "Gateway publica su mapa de prefijos"),
    ("api", "GET", "/api/health", 200, "Proceso de la Gateway"),
    ("api", "GET", "/api/health/servicios", 200, "Bases de MS1-MS4 vía Gateway"),
    ("api", "GET", "/api/health/servicios/ms1_auth", 200, "Diagnóstico MS1"),
    ("api", "GET", "/api/health/servicios/ms2_taller", 200, "Diagnóstico MS2"),
    ("api", "GET", "/api/health/servicios/ms3_presupuestos", 200, "Diagnóstico MS3"),
    ("api", "GET", "/api/health/servicios/ms4_evidencias", 200, "Diagnóstico MS4 (incluye MinIO)"),
    ("api", "GET", "/docs", 200, "Swagger UI"),
    ("api", "GET", "/openapi.json", 200, "Contrato OpenAPI"),
    ("api", "GET", "/api/auth/me", 401, "MS1 exige JWT"),
    ("api", "GET", "/api/vehiculos", 401, "MS2 exige JWT"),
    ("api", "GET", "/api/ordenes", 401, "MS2 exige JWT"),
    ("api", "GET", "/api/presupuestos", 401, "MS3 exige JWT"),
    ("api", "GET", "/api/repuestos", 401, "MS3 exige JWT"),
    ("api", "GET", "/api/evidencias", 401, "MS4 exige JWT"),
    ("api", "POST", "/api/auth/login", 422, "Login valida el cuerpo (sin credenciales)"),
    ("api", "GET", "/api/no-existe", 404, "Formato común de error de la Gateway"),
    ("web", "GET", "/", 200, "Web servida por Nginx"),
    ("web", "GET", "/api/health", 200, "Proxy /api de la web hacia la Gateway"),
)


def consultar(base: str, metodo: str, ruta: str, timeout: float) -> dict:
    datos = b"{}" if metodo == "POST" else None
    peticion = urllib.request.Request(
        base.rstrip("/") + ruta, data=datos, method=metodo,
        headers={"Content-Type": "application/json", "User-Agent": "sgtm-evidencia/1.0"},
    )
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            codigo, cabeceras, cuerpo = respuesta.status, respuesta.headers, respuesta.read()
    except urllib.error.HTTPError as error:
        codigo, cabeceras, cuerpo = error.code, error.headers, error.read()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"codigo": None, "error": type(error).__name__}
    resultado = {
        "codigo": codigo,
        "ms": round((time.perf_counter() - inicio) * 1000),
        "request_id": cabeceras.get("x-request-id"),
        "hsts": bool(cabeceras.get("strict-transport-security")),
        "content_type": (cabeceras.get("content-type") or "").split(";")[0],
    }
    if ruta == "/openapi.json" and codigo == 200:
        contrato = json.loads(cuerpo)
        resultado["openapi"] = {
            "titulo": contrato.get("info", {}).get("title"),
            "version": contrato.get("info", {}).get("version"),
            "rutas": len(contrato.get("paths", {})),
        }
    elif "json" in resultado["content_type"] and len(cuerpo) < 2000:
        try:
            resultado["cuerpo"] = json.loads(cuerpo)
        except ValueError:
            resultado["cuerpo"] = None
    return resultado


def registrar(api: str, web: str, timeout: float = 15.0) -> dict:
    bases = {"api": api, "web": web}
    reporte = {
        "api": api,
        "web": web,
        "registrado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "endpoints": [],
    }
    for origen, metodo, ruta, esperado, demuestra in ENDPOINTS:
        resultado = consultar(bases[origen], metodo, ruta, timeout)
        reporte["endpoints"].append({
            "origen": origen, "metodo": metodo, "ruta": ruta, "esperado": esperado,
            "demuestra": demuestra, "ok": resultado.get("codigo") == esperado, **resultado,
        })
    return reporte


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default=API)
    parser.add_argument("--web", default=WEB)
    parser.add_argument("--json", type=Path, help="guardar el reporte completo en este archivo")
    args = parser.parse_args(argv)

    reporte = registrar(args.api, args.web)
    print(f"Evidencia del despliegue · {reporte['registrado_en']}")
    for e in reporte["endpoints"]:
        marca = "OK" if e["ok"] else "FALLA"
        codigo = e.get("codigo") or e.get("error")
        print(f"  [{marca:^5}] {e['origen']:3} {e['metodo']:4} {e['ruta']:42} {codigo!s:>4} "
              f"(esperado {e['esperado']}) {e.get('ms', '-')} ms")
    fallas = sum(not e["ok"] for e in reporte["endpoints"])
    print(f"\n{len(reporte['endpoints']) - fallas}/{len(reporte['endpoints'])} endpoints como se esperaba.")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Reporte guardado en {args.json}")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
