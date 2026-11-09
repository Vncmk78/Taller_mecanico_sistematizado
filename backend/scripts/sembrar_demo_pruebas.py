"""Escenarios de demostración del ambiente de pruebas, creados por la API.

Deja vehículos del Cliente de prueba con órdenes en cada estado alcanzable con
los endpoints implementados hoy. Todo pasa por la Gateway con los tokens de las
cuentas de `seed_usuarios_prueba.py`: las identidades salen del JWT, las fechas
del servidor y los estados de las transiciones reales. No escribe en ninguna
base de forma directa ni altera estados o fechas directamente. Los escenarios de nueva atención y
devolución se agregan con `sembrar_nuevas_atenciones_demo.py`.

Patentes fijas (reproducible): sobre un ambiente recién construido produce
siempre los mismos escenarios. Si ya están todas, no hace nada; si solo hay
algunas, se detiene y pide reconstruir el ambiente.

Usar con `python scripts/ambiente_pruebas.py sembrar` (verifica el destino).
"""
from __future__ import annotations

import argparse
import json
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
    _decidir,
    _estado,
    _orden_asignada,
    _presupuesto_enviado,
)

MAX_INGRESOS_DIARIOS = 60
MAX_ORDENES_POR_MECANICO = 20

# patente, marca, modelo, año, estado final de su orden (None: sin orden)
ESCENARIOS = [
    ("DEMO01", "Toyota", "Yaris", 2019, 1),     # Recibido, sin mecánico
    ("DEMO02", "Kia", "Rio", 2020, 2),          # Asignado
    ("DEMO03", "Hyundai", "Accent", 2018, 3),   # Esperando aprobación del presupuesto
    ("DEMO04", "Chevrolet", "Sail", 2021, 5),   # En reparación (presupuesto aprobado)
    ("DEMO05", "Nissan", "Versa", 2017, 6),     # Listo para entrega
    ("DEMO06", "Suzuki", "Swift", 2022, 7),     # Entregado
    ("DEMO07", "Peugeot", "208", 2020, "8C"),   # Cancelado a pedido del Cliente
    ("DEMO08", "Mazda", "3", 2016, "8R"),       # Cancelado por rechazo del presupuesto
    ("DEMO09", "Ford", "Fiesta", 2015, None),    # Sin orden: para registrar un ingreso
]


def _configurar(r: Recorrido, admin: str) -> None:
    for ruta, campo, valor in (
        ("/api/ordenes/configuracion/capacidad/ingresos-diarios", "max_ingresos_diarios",
         MAX_INGRESOS_DIARIOS),
        ("/api/ordenes/configuracion/capacidad/mecanicos", "max_ordenes_activas",
         MAX_ORDENES_POR_MECANICO),
    ):
        actual = r.llamar(f"Consulta {campo}", "get", ruta, ruta, 200, admin)
        if actual.get(campo) is None:
            r.llamar(f"Fija {campo}={valor}", "put", ruta, ruta, 200, admin, json={campo: valor})


def _escenario(r: Recorrido, tokens: dict[str, str], patente: str, marca: str, modelo: str,
               anio: int, final) -> None:
    vehiculo = r.llamar(f"{patente}: Cliente registra el vehículo", "post", "/api/vehiculos",
                        "/api/vehiculos", 201, tokens["cliente"],
                        json={"patente": patente, "marca": marca, "modelo": modelo,
                              "anio": anio, "kilometraje": 40000 + anio})
    if final is None:
        return
    vehiculo_id = vehiculo["vehiculo_id"]
    if final == 1:
        r.llamar(f"{patente}: Administrador registra ingreso y orden", "post", "/api/ordenes",
                 "/api/ordenes", 201, tokens["administrador"], json={"vehiculo_id": vehiculo_id})
        return
    if final == "8C":
        orden = r.llamar(f"{patente}: Administrador registra ingreso y orden", "post",
                         "/api/ordenes", "/api/ordenes", 201, tokens["administrador"],
                         json={"vehiculo_id": vehiculo_id})
        base = f"/api/ordenes/{orden['orden_id']}"
        r.llamar(f"{patente}: Cliente solicita cancelar", "post",
                 "/api/ordenes/{orden_id}/cancelacion", f"{base}/cancelacion", 201,
                 tokens["cliente"], json={"motivo": "El cliente decidió no continuar"})
        _estado(r, r.llamar(f"{patente}: Administrador confirma la cancelación", "post",
                            "/api/ordenes/{orden_id}/cancelacion/confirmacion",
                            f"{base}/cancelacion/confirmacion", 200, tokens["administrador"]), 8)
        return

    orden_id = _orden_asignada(r, tokens, vehiculo_id)
    if final == 2:
        return
    presupuesto_id = _presupuesto_enviado(r, tokens, orden_id)
    if final == 3:
        return
    if final == "8R":
        _decidir(r, tokens, presupuesto_id,
                 {"decision": "rechazado", "motivo": "Prefiero no reparar por ahora",
                  "confirmar_cancelacion": True}, f"{patente}: Cliente rechaza el presupuesto")
        _estado(r, r.llamar(f"{patente}: orden cancelada", "get", "/api/ordenes/{orden_id}",
                            f"/api/ordenes/{orden_id}", 200, tokens["administrador"]), 8)
        return
    _decidir(r, tokens, presupuesto_id, {"decision": "aprobado"},
             f"{patente}: Cliente aprueba el presupuesto")
    base = f"/api/ordenes/{orden_id}"
    _estado(r, r.llamar(f"{patente}: orden en reparación", "get", "/api/ordenes/{orden_id}",
                        base, 200, tokens["mecanico"]), 5)
    if final == 5:
        return
    _estado(r, r.llamar(f"{patente}: Mecánico deja la orden lista", "patch",
                        "/api/ordenes/{orden_id}/estado", f"{base}/estado", 200,
                        tokens["mecanico"], json={"estado_destino": 6}), 6)
    if final == 6:
        return
    _estado(r, r.llamar(f"{patente}: Administrador registra la entrega", "post",
                        "/api/ordenes/{orden_id}/entrega", f"{base}/entrega", 200,
                        tokens["administrador"], json={}), 7)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway", required=True)
    args = parser.parse_args()

    indice = httpx.get(f"{args.gateway}/openapi.json", timeout=30).json()
    version = indice["info"]["version"]
    contrato = json.loads(
        (BACKEND_DIR / "docs" / "openapi" / f"sgtm-gateway-{version}.json").read_text("utf-8")
    )
    r = Recorrido(args.gateway, contrato)
    try:
        tokens = {"cliente": r.login(CLIENTE), "mecanico": r.login(MECANICO),
                  "administrador": r.login(ADMINISTRADOR)}
        existentes = {v["patente"] for v in r.llamar(
            "Cliente lista sus vehículos", "get", "/api/vehiculos", "/api/vehiculos", 200,
            tokens["cliente"])}
        demo = {e[0] for e in ESCENARIOS}
        if demo <= existentes:
            print("Los escenarios de demostración ya existen; no se crea nada.")
            return 0
        if demo & existentes:
            print("Solo existen algunos escenarios (" + ", ".join(sorted(demo & existentes))
                  + "). Reconstruir el ambiente de pruebas para dejarlo reproducible.")
            return 1
        _configurar(r, tokens["administrador"])
        for escenario in ESCENARIOS:
            _escenario(r, tokens, *escenario)
    except FalloDePaso:
        pass

    for paso in r.pasos:
        if not paso.ok:
            print(f"FALLA {paso.nombre}: {'; '.join(paso.errores)}")
    if r.pasos and all(p.ok for p in r.pasos):
        print(f"Escenarios de demostración creados ({len(ESCENARIOS)} vehículos, "
              f"{len(r.pasos)} llamadas validadas contra el contrato {version}).")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
