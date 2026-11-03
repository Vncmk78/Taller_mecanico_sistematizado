"""Flujos end-to-end representativos a través de la API Gateway (Semana 8).

Recorre, contra una Gateway levantada con sus cuatro microservicios y bases
PostgreSQL reales, los flujos que usan los clientes web y móvil:

  F1  Acceso: registro, login y usuario actual.
  F0  Configuración del taller: si faltan, el Administrador fija el cupo diario
      de ingresos y el máximo de órdenes activas por mecánico (sin ellos MS2
      no recibe vehículos). Si ya existen, no los cambia.
  F2  Orden completa: el Administrador crea y asigna la orden; el Mecánico
      registra bitácora, sube evidencia y presupuesta; el Administrador envía el
      presupuesto; el Cliente revisa la evidencia y aprueba; el Mecánico
      repara y deja la orden lista; el Administrador entrega; el Cliente ve el
      historial completo de la orden y del vehículo.
  F3  Rechazo del primer presupuesto: la orden queda cancelada.
  F4  Cancelación solicitada por el Cliente y confirmada por el Administrador.
  F5  Seguridad: sin token, rol incorrecto y recursos ajenos.

Cada paso comprueba el estado HTTP esperado y valida el cuerpo contra el
contrato congelado `docs/openapi/sgtm-gateway-<versión>.json` (jsonschema).
Crea datos nuevos en cada corrida (patentes y correos únicos): usar solo
contra bases de desarrollo o integración, nunca producción.

Requiere las cuentas de `scripts/seed_usuarios_prueba.py` y el catálogo de
`scripts/seed_datos_ms3.py` en las bases a las que apunta la Gateway.

Uso, desde backend/:
    python scripts/flujos_e2e_gateway.py [--gateway http://localhost:8000]
                                         [--salida reporte.md]

Sale con 0 si todos los pasos pasan y con 1 si alguno falla.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from jsonschema import Draft202012Validator

BACKEND_DIR = Path(__file__).resolve().parents[1]

CLIENTE = ("cliente@pruebas.cl", "ClientePrueba123!")
MECANICO = ("mecanico@pruebas.cl", "MecanicoPrueba123!")
ADMINISTRADOR = ("administrador@pruebas.cl", "AdminPrueba123!")

# JPEG mínimo válido (SOI + APP0 JFIF + relleno + EOI): MS4 valida la firma.
_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    + b"\x00" * 2000
    + b"\xff\xd9"
)


@dataclass
class Paso:
    flujo: str
    nombre: str
    metodo: str
    ruta: str
    esperado: tuple[int, ...]
    estado: int = 0
    ms: int = 0
    errores: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.estado in self.esperado and not self.errores


class FalloDePaso(Exception):
    """Un paso del que dependen los siguientes no respondió lo esperado."""


class Recorrido:
    def __init__(self, gateway: str, contrato: dict) -> None:
        self.http = httpx.Client(base_url=gateway, timeout=60.0)
        self.contrato = contrato
        self.pasos: list[Paso] = []
        self.flujo = ""
        self.reintentos = 0

    # ── llamadas ──────────────────────────────────────────────────────────
    def llamar(
        self,
        nombre: str,
        metodo: str,
        ruta: str,
        url: str,
        esperado: int | tuple[int, ...],
        token: str | None = None,
        critico: bool = True,
        **kwargs: Any,
    ) -> Any:
        esperados = (esperado,) if isinstance(esperado, int) else esperado
        paso = Paso(self.flujo, nombre, metodo.upper(), ruta, esperados)
        cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
        inicio = time.perf_counter()
        try:
            respuesta = self.http.request(metodo, url, headers=cabeceras, **kwargs)
        except httpx.HTTPError as exc:
            paso.errores.append(f"sin respuesta ({type(exc).__name__})")
            self.pasos.append(paso)
            raise FalloDePaso(nombre) from exc
        paso.ms = int((time.perf_counter() - inicio) * 1000)
        paso.estado = respuesta.status_code
        cuerpo = respuesta.json() if respuesta.content else None
        if paso.estado not in esperados:
            detalle = cuerpo.get("detail") if isinstance(cuerpo, dict) else cuerpo
            paso.errores.append(f"esperaba {esperados}, respondió {paso.estado}: {str(detalle)[:160]}")
        else:
            paso.errores += self._validar(metodo.lower(), ruta, paso.estado, cuerpo)
        self.pasos.append(paso)
        if critico and not paso.ok:
            raise FalloDePaso(nombre)
        return cuerpo

    def _validar(self, metodo: str, ruta: str, estado: int, cuerpo: Any) -> list[str]:
        operacion = self.contrato["paths"].get(ruta, {}).get(metodo)
        if operacion is None:
            return [f"{metodo.upper()} {ruta} no está en el contrato publicado"]
        respuesta = operacion["responses"].get(str(estado))
        if respuesta is None:
            return [f"el estado {estado} no está publicado"]
        esquema = respuesta.get("content", {}).get("application/json", {}).get("schema")
        if esquema is None or cuerpo is None:
            return []
        validador = Draft202012Validator({**esquema, "components": self.contrato["components"]})
        return [
            f"contrato: {'/'.join(map(str, e.absolute_path)) or '(raíz)'}: {e.message[:140]}"
            for e in validador.iter_errors(cuerpo)
        ]

    def login(self, cuenta: tuple[str, str]) -> str:
        cuerpo = self.llamar(
            f"Login {cuenta[0]}", "post", "/api/auth/login", "/api/auth/login", 200,
            json={"email": cuenta[0], "password": cuenta[1]},
        )
        return cuerpo["access_token"]

    def usuario_id(self, token: str) -> int:
        return self.llamar("Usuario actual", "get", "/api/auth/me", "/api/auth/me", 200, token)["id"]

    def correr(self, flujo: str, funcion, *args) -> Any:
        self.flujo = flujo
        try:
            return funcion(self, *args)
        except FalloDePaso:
            return None


# ── flujos ──────────────────────────────────────────────────────────────────


def f1_acceso(r: Recorrido) -> dict[str, str]:
    correo = f"e2e-{secrets.token_hex(4)}@pruebas.cl"
    r.llamar("Registro de cliente nuevo", "post", "/api/auth/register", "/api/auth/register", 201,
             json={"email": correo, "password": "ClaveE2E-12345!", "full_name": "Cliente E2E"})
    r.llamar("Registro con correo repetido", "post", "/api/auth/register", "/api/auth/register",
             409, critico=False,
             json={"email": correo, "password": "ClaveE2E-12345!", "full_name": "Cliente E2E"})
    r.llamar("Login con contraseña incorrecta", "post", "/api/auth/login", "/api/auth/login", 401,
             critico=False, json={"email": correo, "password": "incorrecta-123"})
    nuevo = r.login((correo, "ClaveE2E-12345!"))
    r.usuario_id(nuevo)
    return {
        "cliente_nuevo": nuevo,
        "cliente": r.login(CLIENTE),
        "mecanico": r.login(MECANICO),
        "administrador": r.login(ADMINISTRADOR),
    }


def f0_configuracion(r: Recorrido, tokens: dict[str, str]) -> None:
    for ruta, campo, valor in (
        ("/api/ordenes/configuracion/capacidad/ingresos-diarios", "max_ingresos_diarios", 50),
        ("/api/ordenes/configuracion/capacidad/mecanicos", "max_ordenes_activas", 10),
    ):
        actual = r.llamar(f"Administrador consulta {campo}", "get", ruta, ruta, 200,
                          tokens["administrador"])
        if actual.get(campo) is None:
            r.llamar(f"Administrador fija {campo}={valor}", "put", ruta, ruta, 200,
                     tokens["administrador"], json={campo: valor})


def _vehiculo(r: Recorrido, tokens: dict[str, str]) -> int:
    patente = "E2E" + secrets.token_hex(2).upper()
    vehiculo = r.llamar(
        "Cliente registra vehículo", "post", "/api/vehiculos", "/api/vehiculos", 201,
        tokens["cliente"],
        json={"patente": patente, "marca": "Toyota", "modelo": "Yaris", "anio": 2020,
              "kilometraje": 51000},
    )
    return vehiculo["vehiculo_id"]


def _orden_asignada(r: Recorrido, tokens: dict[str, str], vehiculo_id: int) -> int:
    orden = r.llamar("Administrador crea la orden", "post", "/api/ordenes", "/api/ordenes", 201,
                     tokens["administrador"], json={"vehiculo_id": vehiculo_id})
    orden_id = orden["orden_id"]
    mecanico_id = r.usuario_id(tokens["mecanico"])
    asignada = r.llamar(
        "Administrador asigna mecánico", "put", "/api/ordenes/{orden_id}/mecanico",
        f"/api/ordenes/{orden_id}/mecanico", 200, tokens["administrador"],
        json={"mecanico_id": mecanico_id},
    )
    _estado(r, asignada, 2)
    return orden_id


def _estado(r: Recorrido, orden: dict, esperado: int) -> None:
    if orden.get("estado_codigo") != esperado:
        r.pasos[-1].errores.append(
            f"estado de la orden {orden.get('estado_codigo')}, se esperaba {esperado}"
        )
        raise FalloDePaso("estado")


def _presupuesto_enviado(r: Recorrido, tokens: dict[str, str], orden_id: int) -> int:
    repuestos = r.llamar("Mecánico consulta repuestos", "get", "/api/repuestos", "/api/repuestos",
                         200, tokens["mecanico"])
    lista = repuestos if isinstance(repuestos, list) else repuestos.get("repuestos", repuestos.get("items", []))
    con_stock = [x for x in lista if (x.get("stock_disponible") or x.get("stock") or 0) >= 1]
    items = [{"tipo": "mano_de_obra", "descripcion": "Diagnóstico y mano de obra",
              "cantidad": "1", "precio_unitario": "25000"}]
    if con_stock:
        items.insert(0, {"tipo": "repuesto", "descripcion": con_stock[0]["nombre"],
                         "cantidad": "1", "precio_unitario": "38990",
                         "repuesto_id": con_stock[0]["repuesto_id"]})
    presupuesto = r.llamar("Mecánico crea el presupuesto", "post", "/api/presupuestos",
                           "/api/presupuestos", 201, tokens["mecanico"],
                           json={"orden_id": orden_id, "items": items})
    presupuesto_id = presupuesto["presupuesto_id"]
    r.llamar(
        "Administrador envía el presupuesto", "post",
        "/api/presupuestos/{presupuesto_id}/versiones/{numero}/envio",
        f"/api/presupuestos/{presupuesto_id}/versiones/1/envio", (200, 503),
        tokens["administrador"],
    )
    if r.pasos[-1].estado == 503:
        # El envío quedó guardado y MS2 no confirmó a tiempo: el contrato indica
        # reintentar la aplicación (idempotente), nunca volver a enviar.
        r.reintentos += 1
        r.llamar(
            "Administrador reintenta la aplicación del envío", "post",
            "/api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion",
            f"/api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion", 200,
            tokens["administrador"],
        )
    _estado(r, r.llamar("La orden pasa a esperando aprobación", "get", "/api/ordenes/{orden_id}",
                        f"/api/ordenes/{orden_id}", 200, tokens["administrador"]), 3)
    return presupuesto_id


def _decidir(r: Recorrido, tokens: dict[str, str], presupuesto_id: int, cuerpo: dict,
             nombre: str) -> dict:
    decision = r.llamar(
        nombre, "post", "/api/presupuestos/{presupuesto_id}/versiones/{numero}/decision",
        f"/api/presupuestos/{presupuesto_id}/versiones/1/decision", (201, 503),
        tokens["cliente"], json=cuerpo,
    )
    if r.pasos[-1].estado == 503:
        # Decisión guardada, aplicación pendiente: se reintenta la misma decisión.
        r.reintentos += 1
        r.llamar(
            "Cliente reintenta la aplicación de su decisión", "post",
            "/api/presupuestos/decisiones/{decision_id}/aplicacion",
            f"/api/presupuestos/decisiones/{decision['decision_id']}/aplicacion", 200,
            tokens["cliente"],
        )
    return decision


def f2_orden_completa(r: Recorrido, tokens: dict[str, str]) -> None:
    vehiculo_id = _vehiculo(r, tokens)
    r.llamar("Cliente lista sus vehículos", "get", "/api/vehiculos", "/api/vehiculos", 200,
             tokens["cliente"])
    orden_id = _orden_asignada(r, tokens, vehiculo_id)
    base = f"/api/ordenes/{orden_id}"
    r.llamar("Mecánico ve sus vehículos asignados", "get", "/api/vehiculos/asignados",
             "/api/vehiculos/asignados", 200, tokens["mecanico"])
    r.llamar("Mecánico registra observación", "post", "/api/ordenes/{orden_id}/bitacora",
             f"{base}/bitacora", 201, tokens["mecanico"],
             json={"tipo": "observacion", "descripcion": "Ruido al frenar en el eje delantero"})
    evidencia = r.llamar(
        "Mecánico sube evidencia de diagnóstico", "post", "/api/evidencias", "/api/evidencias",
        201, tokens["mecanico"],
        data={"orden_id": str(orden_id), "contexto": "diagnostico", "visible_cliente": "true"},
        files={"archivo": ("diagnostico.jpg", _JPEG, "image/jpeg")},
    )
    presupuesto_id = _presupuesto_enviado(r, tokens, orden_id)
    _estado(r, r.llamar("Cliente ve la orden esperando aprobación", "get",
                        "/api/ordenes/{orden_id}", base, 200, tokens["cliente"]), 3)
    r.llamar("Cliente lista evidencias de la orden", "get", "/api/evidencias", "/api/evidencias",
             200, tokens["cliente"], params={"orden_id": orden_id})
    r.llamar("Cliente pide URL de descarga", "get", "/api/evidencias/{evidencia_id}/descarga",
             f"/api/evidencias/{evidencia['evidencia_id']}/descarga", 200, tokens["cliente"])
    r.llamar("Cliente busca el presupuesto de la orden", "get", "/api/presupuestos",
             "/api/presupuestos", 200, tokens["cliente"], params={"orden_id": orden_id})
    r.llamar("Cliente ve el detalle del presupuesto", "get", "/api/presupuestos/{presupuesto_id}",
             f"/api/presupuestos/{presupuesto_id}", 200, tokens["cliente"])
    decision = _decidir(r, tokens, presupuesto_id, {"decision": "aprobado"},
                        "Cliente aprueba el presupuesto")
    efecto = decision.get("efecto_en_orden")
    orden = r.llamar("Orden tras la aprobación", "get", "/api/ordenes/{orden_id}", base, 200,
                     tokens["mecanico"])
    if orden["estado_codigo"] == 4:  # esperando repuestos
        r.pasos[-1].errores.append(f"quedó esperando repuestos (efecto={efecto})")
        raise FalloDePaso("stock")
    _estado(r, orden, 5)
    r.llamar("Mecánico registra la reparación", "post", "/api/ordenes/{orden_id}/bitacora",
             f"{base}/bitacora", 201, tokens["mecanico"],
             json={"tipo": "accion", "descripcion": "Se reemplazaron las pastillas",
                   "repuestos": [{"nombre": "Pastillas de freno", "cantidad": 2}]})
    _estado(r, r.llamar("Mecánico deja la orden lista", "patch", "/api/ordenes/{orden_id}/estado",
                        f"{base}/estado", 200, tokens["mecanico"], json={"estado_destino": 6}), 6)
    _estado(r, r.llamar("Administrador registra la entrega", "post",
                        "/api/ordenes/{orden_id}/entrega", f"{base}/entrega", 200,
                        tokens["administrador"], json={}), 7)
    historial = r.llamar("Cliente ve el historial de la orden", "get",
                         "/api/ordenes/{orden_id}/historial", f"{base}/historial", 200,
                         tokens["cliente"])
    recorrido = [h["estado_nuevo"] for h in historial]
    if recorrido != [1, 2, 3, 5, 6, 7]:
        r.pasos[-1].errores.append(f"historial {recorrido}, se esperaba [1, 2, 3, 5, 6, 7]")
    r.llamar("Cliente ve la bitácora", "get", "/api/ordenes/{orden_id}/bitacora",
             f"{base}/bitacora", 200, tokens["cliente"])
    r.llamar("Cliente ve el historial del vehículo", "get",
             "/api/ordenes/vehiculo/{vehiculo_id}/historial",
             f"/api/ordenes/vehiculo/{vehiculo_id}/historial", 200, tokens["cliente"],
             params={"limit": 10, "offset": 0})


def f3_rechazo(r: Recorrido, tokens: dict[str, str]) -> None:
    orden_id = _orden_asignada(r, tokens, _vehiculo(r, tokens))
    presupuesto_id = _presupuesto_enviado(r, tokens, orden_id)
    _decidir(r, tokens, presupuesto_id,
             {"decision": "rechazado", "motivo": "Prefiero no reparar por ahora",
              "confirmar_cancelacion": True},
             "Cliente rechaza el primer presupuesto")
    _estado(r, r.llamar("Orden cancelada por el rechazo", "get", "/api/ordenes/{orden_id}",
                        f"/api/ordenes/{orden_id}", 200, tokens["cliente"]), 8)


def f4_cancelacion(r: Recorrido, tokens: dict[str, str]) -> None:
    orden = r.llamar("Administrador crea la orden", "post", "/api/ordenes", "/api/ordenes", 201,
                     tokens["administrador"], json={"vehiculo_id": _vehiculo(r, tokens)})
    base = f"/api/ordenes/{orden['orden_id']}"
    motivo = {"motivo": "El cliente no continuará"}
    r.llamar("Cliente solicita la cancelación", "post", "/api/ordenes/{orden_id}/cancelacion",
             f"{base}/cancelacion", 201, tokens["cliente"], json=motivo)
    r.llamar("Cliente repite la solicitud", "post", "/api/ordenes/{orden_id}/cancelacion",
             f"{base}/cancelacion", 200, tokens["cliente"], json=motivo)
    r.llamar("Administrador ve cancelaciones pendientes", "get",
             "/api/ordenes/cancelaciones/pendientes", "/api/ordenes/cancelaciones/pendientes",
             200, tokens["administrador"])
    _estado(r, r.llamar("Administrador confirma la cancelación", "post",
                        "/api/ordenes/{orden_id}/cancelacion/confirmacion",
                        f"{base}/cancelacion/confirmacion", 200, tokens["administrador"]), 8)


def f5_seguridad(r: Recorrido, tokens: dict[str, str]) -> None:
    orden = r.llamar("Administrador crea la orden", "post", "/api/ordenes", "/api/ordenes", 201,
                     tokens["administrador"], json={"vehiculo_id": _vehiculo(r, tokens)})
    base = f"/api/ordenes/{orden['orden_id']}"
    r.llamar("Sin token", "get", "/api/ordenes", "/api/ordenes", 401, critico=False)
    r.llamar("Token inválido", "get", "/api/auth/me", "/api/auth/me", 401, "token.invalido",
             critico=False)
    r.llamar("Otro cliente no ve la orden ajena", "get", "/api/ordenes/{orden_id}", base, 404,
             tokens["cliente_nuevo"], critico=False)
    r.llamar("Mecánico no asignado no ve la orden", "get", "/api/ordenes/{orden_id}", base, 404,
             tokens["mecanico"], critico=False)
    r.llamar("Cliente no puede cambiar el estado", "patch", "/api/ordenes/{orden_id}/estado",
             f"{base}/estado", 403, tokens["cliente"], critico=False, json={"estado_destino": 2})
    r.llamar("Mecánico no puede crear órdenes", "post", "/api/ordenes", "/api/ordenes", 403,
             tokens["mecanico"], critico=False, json={"vehiculo_id": 1})
    r.llamar("Cliente no puede listar usuarios", "get", "/api/auth/usuarios",
             "/api/auth/usuarios", 403, tokens["cliente"], critico=False)
    r.llamar("Body inválido", "post", "/api/vehiculos", "/api/vehiculos", 422, tokens["cliente"],
             critico=False, json={})


# ── reporte ─────────────────────────────────────────────────────────────────


def reporte(r: Recorrido, version: str, gateway: str, segundos: float) -> str:
    ok = sum(p.ok for p in r.pasos)
    lineas = [
        f"# Flujos E2E a través de la Gateway — contrato {version}",
        "",
        f"Gateway: `{gateway}` · Pasos: **{ok}/{len(r.pasos)} OK** · Duración: {segundos:.1f} s"
        f" · Reintentos de coordinación MS3 → MS2: {r.reintentos}",
        "",
        "| Flujo | Paso | Llamada | Esperado | Obtenido | ms | Resultado |",
        "|---|---|---|---|---|---:|---|",
    ]
    for p in r.pasos:
        resultado = "OK" if p.ok else "FALLA: " + "; ".join(p.errores).replace("|", "/")
        esperado = "/".join(map(str, p.esperado))
        lineas.append(
            f"| {p.flujo} | {p.nombre} | `{p.metodo} {p.ruta}` | {esperado} | {p.estado} "
            f"| {p.ms} | {resultado} |"
        )
    return "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Flujos E2E a través de la API Gateway")
    parser.add_argument("--gateway", default="http://localhost:8000")
    parser.add_argument("--salida", type=Path, help="guarda el reporte en Markdown")
    parser.add_argument(
        "--flujos", default="F2,F3,F4,F5",
        help="flujos a correr además de F1 y F0, separados por coma (por defecto todos)",
    )
    args = parser.parse_args()

    indice = httpx.get(f"{args.gateway}/openapi.json", timeout=30).json()
    version = indice["info"]["version"]
    archivo = BACKEND_DIR / "docs" / "openapi" / f"sgtm-gateway-{version}.json"
    contrato = json.loads(archivo.read_text(encoding="utf-8"))

    r = Recorrido(args.gateway, contrato)
    inicio = time.perf_counter()
    tokens = r.correr("F1 Acceso", f1_acceso)
    if tokens:
        r.correr("F0 Configuración", f0_configuracion, tokens)
        elegidos = {f.strip().upper() for f in args.flujos.split(",") if f.strip()}
        for clave, nombre, funcion in (
            ("F2", "F2 Orden completa", f2_orden_completa),
            ("F3", "F3 Rechazo", f3_rechazo),
            ("F4", "F4 Cancelación", f4_cancelacion),
            ("F5", "F5 Seguridad", f5_seguridad),
        ):
            if clave in elegidos:
                r.correr(nombre, funcion, tokens)
    texto = reporte(r, version, args.gateway, time.perf_counter() - inicio)
    print(texto)
    if args.salida:
        args.salida.write_text(texto, encoding="utf-8")
    return 0 if r.pasos and all(p.ok for p in r.pasos) else 1


if __name__ == "__main__":
    sys.exit(main())
