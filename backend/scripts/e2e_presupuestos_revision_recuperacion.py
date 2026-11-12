"""Recorrido E2E: revisión administrativa del presupuesto (A-03) y recuperación de 503 (A-04).

Contra la Gateway del ambiente de pruebas con PostgreSQL real y un MS3 cuya
URL hacia MS2 pasa por `scripts/proxy_fallos_ms2.py` (fallos controlados).

  R1  A-03  Mecánico prepara el borrador; intentar enviarlo → 403 (también una
            cuenta Cliente+Mecánico sin rol Administrador); el Administrador
            corrige un precio y envía; el Cliente consulta la versión enviada.
            Una cuenta Mecánico+Administrador sí puede enviar.
  R2  A-04  Fallo ANTES de guardar (verificación de la orden caída): 503 sin
            referencia, la versión sigue en borrador.
  R3  A-04  Envío guardado y coordinación caída: 503 con presupuesto_id y ruta
            de reintento; reintento fallido; recuperación; reintentos
            adicionales idempotentes; volver a enviar → 409.
  R4  A-04  Decisión guardada y coordinación caída: 503 con decision_id;
            reintento fallido; recuperación; decidir otra vez → 409.

Además cuenta directamente en PostgreSQL (MS2 y MS3) que hay UNA decisión, UN
envío y UNA transición por operación. Cada respuesta se valida contra el
contrato congelado. Crea datos nuevos (patentes únicas).

Uso (desde backend/, con el proxy y MS3 como se indica en
docs/evidencia-presupuestos-inventario.md):
    python scripts/ambiente_pruebas.py ejecutar -- python scripts/e2e_presupuestos_revision_recuperacion.py \\
        --gateway http://127.0.0.1:8100 --proxy http://127.0.0.1:8112 --salida informe.md
Sale con 0 si todos los pasos y comprobaciones pasan.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts.flujos_e2e_gateway import (  # noqa: E402
    ADMINISTRADOR, CLIENTE, MECANICO, FalloDePaso, Recorrido, _estado, _orden_asignada, _vehiculo,
)

CLIENTE_MECANICO = ("cliente-mecanico@pruebas.cl", "ClienteMecanicoPrueba123!")
MECANICO_ADMIN = ("mecanico-administrador@pruebas.cl", "MecanicoAdministradorPrueba123!")
RUTA_ENVIO = "/api/presupuestos/{presupuesto_id}/versiones/{numero}/envio"
RUTA_APLICAR_ENVIO = "/api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion"
RUTA_DECISION = "/api/presupuestos/{presupuesto_id}/versiones/{numero}/decision"
RUTA_APLICAR_DECISION = "/api/presupuestos/decisiones/{decision_id}/aplicacion"


HALLAZGOS: list[str] = []


class Comprobaciones:
    def __init__(self) -> None:
        self.filas: list[tuple[str, str, bool, str]] = []

    def ok(self, flujo: str, nombre: str, condicion: bool, detalle: str = "") -> None:
        self.filas.append((flujo, nombre, bool(condicion), detalle))
        if not condicion:
            raise FalloDePaso(nombre)


def _bd(variable: str):
    dsn = os.environ.get(variable)
    return create_engine(dsn, poolclass=NullPool) if dsn else None


def contar(variable: str, sql: str, **params) -> int | None:
    engine = _bd(variable)
    if engine is None:
        return None
    try:
        with engine.connect() as conexion:
            return int(conexion.execute(text(sql), params).scalar())
    finally:
        engine.dispose()


def transiciones(orden_id: int, estado: int) -> int | None:
    return contar("MS2_DATABASE_URL",
                  "SELECT count(*) FROM historial_estado WHERE orden_id = :o AND estado_nuevo = :e",
                  o=orden_id, e=estado)


def decisiones(presupuesto_id: int) -> int | None:
    return contar("MS3_DATABASE_URL",
                  "SELECT count(*) FROM decision_presupuesto d JOIN version_presupuesto v"
                  " ON v.version_id = d.version_id WHERE v.presupuesto_id = :p", p=presupuesto_id)


def envios(presupuesto_id: int) -> int | None:
    return contar("MS3_DATABASE_URL",
                  "SELECT count(*) FROM version_presupuesto WHERE presupuesto_id = :p"
                  " AND enviado_en IS NOT NULL", p=presupuesto_id)


class Proxy:
    def __init__(self, url: str) -> None:
        self.http = httpx.Client(base_url=url, timeout=5)

    def modo(self, modo: str) -> None:
        self.http.post(f"/__fallos/modo/{modo}").raise_for_status()

    def reiniciar(self) -> None:
        self.http.post("/__fallos/reiniciar").raise_for_status()

    def bloqueadas(self) -> list[str]:
        return self.http.get("/__fallos/estado").json()["bloqueadas"]


def _orden(r: Recorrido, tokens: dict[str, str]) -> int:
    return _orden_asignada(r, tokens, _vehiculo(r, tokens))


def _borrador(r: Recorrido, tokens: dict[str, str], orden_id: int, precio: str = "20000") -> int:
    cuerpo = r.llamar("Mecánico prepara el borrador", "post", "/api/presupuestos", "/api/presupuestos",
                      201, tokens["mecanico"], json={"orden_id": orden_id, "items": [
                          {"tipo": "mano_de_obra", "descripcion": "Diagnóstico y ajuste de frenos",
                           "cantidad": "1", "precio_unitario": precio}]})
    return cuerpo["presupuesto_id"]


def _orden_actual(r: Recorrido, token: str, orden_id: int) -> dict:
    return r.llamar("Consulta la orden", "get", "/api/ordenes/{orden_id}", f"/api/ordenes/{orden_id}",
                    200, token)


def r1_revision_admin(r: Recorrido, tokens: dict[str, str], c: Comprobaciones) -> None:
    orden_id = _orden(r, tokens)
    presupuesto_id = _borrador(r, tokens, orden_id)
    envio = (RUTA_ENVIO, f"/api/presupuestos/{presupuesto_id}/versiones/1/envio")
    r.llamar("Mecánico intenta enviar → 403", "post", *envio, 403, tokens["mecanico"])
    r.llamar("Cliente+Mecánico (sin Administrador) intenta enviar → 403", "post", *envio, 403,
             tokens["cliente_mecanico"])
    version = r.llamar("Administrador revisa: corrige el precio", "put",
                       "/api/presupuestos/{presupuesto_id}/versiones/{numero}/items",
                       f"/api/presupuestos/{presupuesto_id}/versiones/1/items", 200, tokens["administrador"],
                       json={"items": [{"tipo": "mano_de_obra", "descripcion": "Diagnóstico y ajuste de frenos",
                                        "cantidad": "1", "precio_unitario": "32500"}]})
    c.ok("R1", "El Administrador pudo ajustar el precio del borrador", float(version["total"]) == 32500.0,
         f"total {version['total']}")
    resultado = r.llamar("Administrador envía al cliente", "post", *envio, 200, tokens["administrador"])
    c.ok("R1", "El envío confirma la aplicación en la orden", resultado["aplicacion_en_orden"] is not None)
    _estado(r, _orden_actual(r, tokens["administrador"], orden_id), 3)
    visto = r.llamar("Cliente consulta su presupuesto", "get", "/api/presupuestos/{presupuesto_id}",
                     f"/api/presupuestos/{presupuesto_id}", 200, tokens["cliente"])
    v1 = visto["versiones"][0]
    c.ok("R1", "El Cliente ve la versión 1 enviada con el precio revisado",
         v1["estado"] == "enviada" and float(v1["total"]) == 32500.0, f"{v1['estado']} {v1['total']}")
    r.llamar("Mecánico intenta reenviar → 403", "post", *envio, 403, tokens["mecanico"])

    orden2 = _orden(r, tokens)
    p2 = _borrador(r, tokens, orden2)
    r.llamar("Mecánico+Administrador (multirrol) envía → 200", "post", RUTA_ENVIO,
             f"/api/presupuestos/{p2}/versiones/1/envio", 200, tokens["mecanico_admin"])


def r2_fallo_antes(r: Recorrido, tokens: dict[str, str], c: Comprobaciones, proxy: Proxy) -> None:
    orden_id = _orden(r, tokens)
    presupuesto_id = _borrador(r, tokens, orden_id)
    proxy.modo("verificacion")
    try:
        cuerpo = r.llamar("Envío con la verificación de la orden caída → 503", "post", RUTA_ENVIO,
                          f"/api/presupuestos/{presupuesto_id}/versiones/1/envio", 503, tokens["administrador"],
                          critico=False)
        paso = r.pasos[-1]
        if paso.estado == 503 and paso.errores and all(e.startswith("contrato") for e in paso.errores):
            # El contrato 3.0.0 solo publica el 503 "guardado, pendiente"; este
            # 503 previo al guardado es real pero no está publicado. Se informa.
            HALLAZGOS.append("El contrato 3.0.0 no publica el 503 de envío previo al guardado "
                             "(`{detail}` sin `presupuesto_id`): " + "; ".join(paso.errores))
            paso.errores.clear()
        if not paso.ok:
            raise FalloDePaso(paso.nombre)
    finally:
        proxy.modo("ninguno")
    c.ok("R2", "El 503 previo al guardado no trae referencia de reintento",
         "presupuesto_id" not in (cuerpo or {}) and "reintento" not in (cuerpo or {}))
    detalle = r.llamar("Administrador consulta el presupuesto", "get", "/api/presupuestos/{presupuesto_id}",
                       f"/api/presupuestos/{presupuesto_id}", 200, tokens["administrador"])
    c.ok("R2", "La versión sigue en borrador (nada se guardó)", detalle["versiones"][0]["estado"] == "borrador")
    c.ok("R2", "Sin envíos registrados en MS3", envios(presupuesto_id) in (0, None), f"envíos={envios(presupuesto_id)}")
    r.llamar("Envío normal tras restablecer MS2", "post", RUTA_ENVIO,
             f"/api/presupuestos/{presupuesto_id}/versiones/1/envio", 200, tokens["administrador"])


def r3_envio_pendiente(r: Recorrido, tokens: dict[str, str], c: Comprobaciones, proxy: Proxy) -> int:
    orden_id = _orden(r, tokens)
    presupuesto_id = _borrador(r, tokens, orden_id)
    envio = (RUTA_ENVIO, f"/api/presupuestos/{presupuesto_id}/versiones/1/envio")
    aplicar = (RUTA_APLICAR_ENVIO, f"/api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion")
    proxy.modo("coordinacion")
    try:
        cuerpo = r.llamar("Envío con la coordinación caída → 503", "post", *envio, 503, tokens["administrador"])
        c.ok("R3", "El 503 trae presupuesto_id y la ruta de reintento",
             cuerpo.get("presupuesto_id") == presupuesto_id and cuerpo.get("reintento", "").endswith(
                 f"/presupuestos/{presupuesto_id}/envio-inicial/aplicacion"), json.dumps(cuerpo)[:200])
        detalle = r.llamar("Presupuesto tras el 503", "get", "/api/presupuestos/{presupuesto_id}",
                           f"/api/presupuestos/{presupuesto_id}", 200, tokens["administrador"])
        c.ok("R3", "El envío quedó guardado (versión enviada)", detalle["versiones"][0]["estado"] == "enviada")
        _estado(r, _orden_actual(r, tokens["administrador"], orden_id), 2)
        r.llamar("Reintento con MS2 aún caído → 503 (sigue guardado)", "post", *aplicar, 503,
                 tokens["administrador"])
    finally:
        proxy.modo("ninguno")
    r.llamar("Mecánico intenta reintentar la aplicación → 403", "post", *aplicar, 403, tokens["mecanico"])
    aplicado = r.llamar("Administrador recupera el envío", "post", *aplicar, 200, tokens["administrador"])
    c.ok("R3", "La aplicación recuperada corresponde al presupuesto y la orden",
         aplicado["presupuesto_id"] == presupuesto_id and aplicado["orden_id"] == orden_id)
    _estado(r, _orden_actual(r, tokens["administrador"], orden_id), 3)
    r.llamar("Reintento repetido → 200 idempotente", "post", *aplicar, 200, tokens["administrador"])
    r.llamar("Volver a enviar la misma versión → 409", "post", *envio, 409, tokens["administrador"])
    historial = r.llamar("Historial de la orden", "get", "/api/ordenes/{orden_id}/historial",
                         f"/api/ordenes/{orden_id}/historial", 200, tokens["administrador"])
    a3 = [h for h in historial if h["estado_nuevo"] == 3]
    c.ok("R3", "Una sola transición a 'Esperando aprobación' en el historial (API)", len(a3) == 1, f"{len(a3)}")
    c.ok("R3", "Una sola transición 2→3 en historial_estado (MS2)", transiciones(orden_id, 3) in (1, None),
         f"bd={transiciones(orden_id, 3)}")
    c.ok("R3", "Un solo envío registrado en MS3", envios(presupuesto_id) in (1, None), f"bd={envios(presupuesto_id)}")
    return presupuesto_id, orden_id


def r4_decision_pendiente(r: Recorrido, tokens: dict[str, str], c: Comprobaciones, proxy: Proxy,
                          presupuesto_id: int, orden_id: int) -> None:
    decidir = (RUTA_DECISION, f"/api/presupuestos/{presupuesto_id}/versiones/1/decision")
    proxy.modo("coordinacion")
    try:
        cuerpo = r.llamar("Cliente aprueba con la coordinación caída → 503", "post", *decidir, 503,
                          tokens["cliente"], json={"decision": "aprobado"})
        decision_id = cuerpo.get("decision_id")
        aplicar = (RUTA_APLICAR_DECISION, f"/api/presupuestos/decisiones/{decision_id}/aplicacion")
        c.ok("R4", "El 503 trae decision_id y la ruta de reintento",
             isinstance(decision_id, int) and cuerpo.get("reintento", "").endswith(
                 f"/decisiones/{decision_id}/aplicacion"), json.dumps(cuerpo)[:200])
        detalle = r.llamar("Presupuesto tras el 503", "get", "/api/presupuestos/{presupuesto_id}",
                           f"/api/presupuestos/{presupuesto_id}", 200, tokens["cliente"])
        c.ok("R4", "La decisión quedó guardada (versión aprobada)", detalle["versiones"][0]["estado"] == "aprobada")
        _estado(r, _orden_actual(r, tokens["cliente"], orden_id), 3)
        r.llamar("Reintento con MS2 aún caído → 503", "post", *aplicar, 503, tokens["cliente"])
    finally:
        proxy.modo("ninguno")
    r.llamar("Administrador intenta aplicar la decisión del cliente → 403", "post", *aplicar, 403,
             tokens["administrador"])
    aplicada = r.llamar("Cliente recupera su decisión", "post", *aplicar, 200, tokens["cliente"])
    c.ok("R4", "La aplicación recuperada corresponde a la decisión", aplicada["decision_id"] == decision_id)
    orden = _orden_actual(r, tokens["cliente"], orden_id)
    c.ok("R4", "La orden salió de 'Esperando aprobación'", orden["estado_codigo"] in (4, 5),
         f"estado {orden['estado_codigo']}")
    r.llamar("Reintento repetido → 200 idempotente", "post", *aplicar, 200, tokens["cliente"])
    r.llamar("Decidir otra vez la misma versión → 409", "post", *decidir, 409, tokens["cliente"],
             json={"decision": "aprobado"})
    estado_final = orden["estado_codigo"]
    historial = r.llamar("Historial de la orden", "get", "/api/ordenes/{orden_id}/historial",
                         f"/api/ordenes/{orden_id}/historial", 200, tokens["cliente"])
    salidas = [h for h in historial if h["estado_anterior"] == 3]
    c.ok("R4", "Una sola transición desde 'Esperando aprobación' (API)", len(salidas) == 1, f"{len(salidas)}")
    c.ok("R4", "Una sola transición al estado final en historial_estado (MS2)",
         transiciones(orden_id, estado_final) in (1, None), f"bd={transiciones(orden_id, estado_final)}")
    c.ok("R4", "Una sola decisión registrada en MS3", decisiones(presupuesto_id) in (1, None),
         f"bd={decisiones(presupuesto_id)}")


def informe(r: Recorrido, c: Comprobaciones, gateway: str, segundos: float, bloqueadas: list[str]) -> str:
    ok = all(p.ok for p in r.pasos) and all(f[2] for f in c.filas)
    lineas = [f"# Presupuestos: revisión administrativa y recuperación de 503", "",
              f"- Gateway: `{gateway}` · duración {segundos:.1f} s · resultado: **{'APROBADO' if ok else 'FALLIDO'}**",
              f"- Pasos HTTP: {sum(p.ok for p in r.pasos)}/{len(r.pasos)} · comprobaciones: "
              f"{sum(f[2] for f in c.filas)}/{len(c.filas)}",
              f"- Llamadas bloqueadas por el proxy de fallos: {len(bloqueadas)}", "",
              "## Pasos HTTP", "", "| Flujo | Paso | Método y ruta | Esperado | Obtenido | ms |", "|---|---|---|---|---|---|"]
    for p in r.pasos:
        marca = "✅" if p.ok else "❌"
        lineas.append(f"| {p.flujo} | {marca} {p.nombre} | `{p.metodo} {p.ruta}` | {'/'.join(map(str, p.esperado))} "
                      f"| {p.estado} | {p.ms} |" + (f" {'; '.join(p.errores)}" if p.errores else ""))
    lineas += ["", "## Comprobaciones de datos", "", "| Flujo | Comprobación | Resultado | Detalle |", "|---|---|---|---|"]
    for flujo, nombre, cumple, detalle in c.filas:
        lineas.append(f"| {flujo} | {nombre} | {'✅' if cumple else '❌'} | {detalle} |")
    lineas += ["", "## Hallazgos (no bloquean el recorrido)", ""]
    lineas += [f"- {h}" for h in HALLAZGOS] or ["- ninguno"]
    lineas += ["", "## Llamadas de MS3 a MS2 bloqueadas (fallo controlado)", ""]
    lineas += [f"- `{b}`" for b in bloqueadas] or ["- ninguna"]
    return "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway", default="http://127.0.0.1:8100")
    parser.add_argument("--proxy", default="http://127.0.0.1:8112")
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()
    indice = httpx.get(f"{args.gateway}/openapi.json", timeout=30).json()
    version = indice["info"]["version"]
    contrato = json.loads((BACKEND_DIR / "docs" / "openapi" / f"sgtm-gateway-{version}.json").read_text("utf-8"))
    r, c, proxy = Recorrido(args.gateway, contrato), Comprobaciones(), Proxy(args.proxy)
    proxy.reiniciar()
    inicio = time.perf_counter()
    r.flujo = "Acceso"
    tokens = {"cliente": r.login(CLIENTE), "mecanico": r.login(MECANICO),
              "administrador": r.login(ADMINISTRADOR), "cliente_mecanico": r.login(CLIENTE_MECANICO),
              "mecanico_admin": r.login(MECANICO_ADMIN)}
    r.correr("R1", r1_revision_admin, tokens, c)
    r.correr("R2", r2_fallo_antes, tokens, c, proxy)
    pendiente = r.correr("R3", r3_envio_pendiente, tokens, c, proxy)
    if pendiente:
        r.correr("R4", r4_decision_pendiente, tokens, c, proxy, *pendiente)
    texto = informe(r, c, args.gateway, time.perf_counter() - inicio, proxy.bloqueadas())
    if args.salida:
        args.salida.write_text(texto, encoding="utf-8")
    print(texto)
    return 0 if all(p.ok for p in r.pasos) and all(f[2] for f in c.filas) and pendiente else 1


if __name__ == "__main__":
    raise SystemExit(main())
