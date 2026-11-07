"""Valida los recorridos implementados en el ambiente de pruebas y reproduce problemas.

Tres secciones, sin mezclar resultados:
1. Recorridos implementados: ejecuta `flujos_e2e_gateway.py` (F1 acceso, F0
   configuración, F2 orden completa, F3 rechazo, F4 cancelación, F5 seguridad),
   que valida cada respuesta contra el contrato congelado.
2. Problemas conocidos: los reproduce por la API con vehículos nuevos (no toca
   los escenarios DEMO). Un problema "REPRODUCIDO" es el comportamiento actual
   que el Bloque 3 debe corregir; no cuenta como recorrido funcional.
3. Pendientes: funciones aprobadas que todavía no existen; solo se comprueba su
   ausencia en el contrato publicado, nunca se simulan.

Sale con 0 si todos los recorridos implementados pasan (los problemas
reproducidos son informativos) y con 1 si alguno falla.
Usar con `python scripts/ambiente_pruebas.py recorridos` (verifica el destino).
"""
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts.flujos_e2e_gateway import (  # noqa: E402
    ADMINISTRADOR,
    CLIENTE,
    MECANICO,
    FalloDePaso,
    Recorrido,
)
from scripts.sembrar_demo_pruebas import _escenario  # noqa: E402


def _patente(prefijo: str) -> str:
    return prefijo + secrets.token_hex(2).upper()


def _crear_orden(r: Recorrido, admin: str, vehiculo_id: int, nombre: str):
    return r.llamar(nombre, "post", "/api/ordenes", "/api/ordenes", (201, 409), admin,
                    critico=False, json={"vehiculo_id": vehiculo_id})


def _vehiculo_id(r: Recorrido, cliente: str, patente: str) -> int:
    vehiculos = r.llamar("Cliente lista sus vehículos", "get", "/api/vehiculos",
                         "/api/vehiculos", 200, cliente)
    return next(v["vehiculo_id"] for v in vehiculos if v["patente"] == patente)


def problemas(r: Recorrido, tokens: dict[str, str]) -> list[tuple[str, str, str]]:
    """(problema, resultado, evidencia) para cada problema conocido."""

    resultados: list[tuple[str, str, str]] = []
    admin = tokens["administrador"]

    # P1 — Dos órdenes activas para el mismo vehículo.
    r.flujo = "P1 Varias órdenes activas"
    patente = _patente("PVA")
    try:
        _escenario(r, tokens, patente, "Kia", "Morning", 2019, 1)
        vehiculo_id = _vehiculo_id(r, tokens["cliente"], patente)
        segunda = _crear_orden(r, admin, vehiculo_id, "Segunda orden con la primera activa")
        if r.pasos[-1].estado == 201:
            resultados.append(("P1 Se acepta una segunda orden activa para el mismo vehículo",
                               "REPRODUCIDO",
                               (f"POST /api/ordenes respondió 201 (orden {segunda['orden_id']}, "
                                f"ingreso {segunda['ingreso_id']} compartido)")))
        else:
            resultados.append(("P1 Se acepta una segunda orden activa para el mismo vehículo",
                               "NO REPRODUCIDO", f"respondió {r.pasos[-1].estado}"))
    except FalloDePaso:
        resultados.append(("P1 Se acepta una segunda orden activa", "SIN DATOS",
                           "falló la preparación"))

    # P2 — La entrega no registra la salida física: el ingreso sigue abierto.
    r.flujo = "P2 Salida no registrada"
    patente = _patente("PSE")
    try:
        _escenario(r, tokens, patente, "Suzuki", "Baleno", 2018, 7)
        vehiculo_id = _vehiculo_id(r, tokens["cliente"], patente)
        historial = r.llamar("Historial del vehículo", "get",
                             "/api/ordenes/vehiculo/{vehiculo_id}/historial",
                             f"/api/ordenes/vehiculo/{vehiculo_id}/historial", 200, admin,
                             params={"limit": 10, "offset": 0})
        items = historial.get("items", historial) if isinstance(historial, dict) else historial
        entregada = next(o for o in items if o.get("estado_codigo") == 7)
        nueva = _crear_orden(r, admin, vehiculo_id, "Nueva orden tras la entrega")
        if r.pasos[-1].estado == 201 and nueva["ingreso_id"] == entregada["ingreso_id"]:
            resultados.append((("P2 La entrega no cierra el ingreso: la orden siguiente lo "
                                "reutiliza sin validar cupo"), "REPRODUCIDO",
                               (f"orden {nueva['orden_id']} usa el ingreso {nueva['ingreso_id']} "
                                f"de la orden entregada {entregada['orden_id']}")))
        else:
            resultados.append(("P2 La entrega no cierra el ingreso", "NO REPRODUCIDO",
                               f"respondió {r.pasos[-1].estado}"))
    except (FalloDePaso, StopIteration, KeyError):
        resultados.append(("P2 La entrega no cierra el ingreso", "SIN DATOS",
                           "falló la preparación o el historial no trae ingreso_id"))
    return resultados


def pendientes(contrato: dict) -> list[tuple[str, str]]:
    rutas = " ".join(contrato["paths"])
    return [
        ("Devolución física de un vehículo con orden cancelada (Bloque 4)",
         "presente en el contrato" if "devolucion" in rutas else "no implementada"),
        ("Solicitud de nueva atención y su revisión (Bloque 3)",
         "presente en el contrato" if "nueva-atencion" in rutas or "solicitudes" in rutas
         else "no implementada"),
        ("Regla de una sola orden activa por vehículo y contrato 3.0.0", "no implementada"),
        ("Registro de salida al entregar o devolver (salida_en)", "no implementado"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()

    reporte_flujos = BACKEND_DIR / ".pruebas" / "flujos_e2e.md"
    reporte_flujos.parent.mkdir(exist_ok=True)
    codigo_flujos = subprocess.run(
        [sys.executable, "scripts/flujos_e2e_gateway.py", "--gateway", args.gateway,
         "--salida", str(reporte_flujos)],
        cwd=BACKEND_DIR, capture_output=True, text=True, check=False,
    ).returncode
    texto_flujos = reporte_flujos.read_text("utf-8") if reporte_flujos.exists() else "(sin reporte)"

    version = httpx.get(f"{args.gateway}/openapi.json", timeout=30).json()["info"]["version"]
    contrato = json.loads(
        (BACKEND_DIR / "docs" / "openapi" / f"sgtm-gateway-{version}.json").read_text("utf-8")
    )
    r = Recorrido(args.gateway, contrato)
    tokens = {"cliente": r.login(CLIENTE), "mecanico": r.login(MECANICO),
              "administrador": r.login(ADMINISTRADOR)}
    encontrados = problemas(r, tokens)
    fallas_preparacion = [p for p in r.pasos if not p.ok and p.estado not in (409,)]

    lineas = [
        f"# Recorridos del ambiente de pruebas — contrato {version}",
        "",
        "## 1. Recorridos implementados (flujos_e2e_gateway.py)",
        "",
        "Resultado: " + ("**todos pasan**" if codigo_flujos == 0 else "**hay fallas**"),
        "",
        texto_flujos.split("\n", 2)[-1] if texto_flujos.startswith("#") else texto_flujos,
        "## 2. Problemas conocidos (comportamiento actual, no funcional)",
        "",
        "| Problema | Resultado | Evidencia |",
        "|---|---|---|",
        *[f"| {p} | {res} | {ev} |" for p, res, ev in encontrados],
        "",
        "## 3. Pendientes (no se simulan)",
        "",
        "| Función | Estado |",
        "|---|---|",
        *[f"| {f} | {e} |" for f, e in pendientes(contrato)],
        "",
    ]
    if fallas_preparacion:
        lineas += ["Fallas al preparar las reproducciones:", ""]
        lineas += [f"- {p.flujo} / {p.nombre}: {'; '.join(p.errores)}" for p in fallas_preparacion]
    texto = "\n".join(lineas) + "\n"
    print(texto)
    if args.salida:
        args.salida.write_text(texto, encoding="utf-8")
    return 0 if codigo_flujos == 0 and not fallas_preparacion else 1


if __name__ == "__main__":
    raise SystemExit(main())
