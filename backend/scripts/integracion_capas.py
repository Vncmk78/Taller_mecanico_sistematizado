"""Integración por capas: Web → Gateway → Microservicios → ORM/BD (Semana 8).

Comprueba, de abajo hacia arriba, que cada capa del SGTM está conectada con la
siguiente en un entorno levantado (servicios reales y PostgreSQL real):

  1. BD       Las cuatro bases tienen aplicadas las migraciones del checkout.
  2. MS       Cada microservicio responde /health y /health/db (ORM → BD).
  3. Gateway  /api/health/servicios ve los cuatro servicios y publica el
              contrato congelado de su versión.
  4. Web      El frontend responde, su proxy /api llega a la Gateway y la
              Gateway acepta el preflight CORS del origen web.
  5. Persistencia  Escrituras hechas por la Gateway (vehículo, orden con su
              historial, usuario, evidencia) se leen directamente en la base de
              cada microservicio con una transacción de solo lectura, y la
              evidencia además en el almacenamiento S3.

Escribe un vehículo, una orden y una evidencia nuevos en cada corrida: usar
solo contra bases de desarrollo o integración, nunca producción.

Variables (mismas que usan los servicios): MS1..MS4_DATABASE_URL y, para la
comprobación del objeto, MS4_S3_ENDPOINT/ACCESS_KEY/SECRET_KEY/BUCKET/REGION.
Requiere las cuentas de scripts/seed_usuarios_prueba.py.

Uso, desde backend/:
    python scripts/integracion_capas.py [--gateway http://localhost:8000]
        [--web http://localhost:5173] [--ms http://localhost:8001,...] [--salida r.md]

Sale con 0 si todas las comprobaciones pasan.
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts.verificar_migraciones import verificar_todas  # noqa: E402

CLIENTE = ("cliente@pruebas.cl", "ClientePrueba123!")
MECANICO = ("mecanico@pruebas.cl", "MecanicoPrueba123!")
ADMINISTRADOR = ("administrador@pruebas.cl", "AdminPrueba123!")
_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    + secrets.token_bytes(512)
    + b"\xff\xd9"
)


class Informe:
    def __init__(self) -> None:
        self.filas: list[tuple[str, str, bool, str]] = []

    def anotar(self, capa: str, comprobacion: str, ok: bool, detalle: str = "") -> bool:
        self.filas.append((capa, comprobacion, ok, detalle))
        return ok

    def markdown(self, titulo: str) -> str:
        ok = sum(f[2] for f in self.filas)
        lineas = [f"# {titulo}", "", f"Comprobaciones: **{ok}/{len(self.filas)} OK**", "",
                  "| Capa | Comprobación | Resultado | Detalle |", "|---|---|---|---|"]
        for capa, nombre, bien, detalle in self.filas:
            lineas.append(f"| {capa} | {nombre} | {'OK' if bien else 'FALLA'} | "
                          f"{detalle.replace('|', '/')} |")
        return "\n".join(lineas) + "\n"


def _sql(servicio: str, consulta: str, **parametros) -> list[tuple]:
    """Lectura en una transacción de solo lectura sobre la base del servicio."""
    entorno = {**dotenv_values(BACKEND_DIR / ".env"), **os.environ}
    engine = create_engine(entorno[f"{servicio}_DATABASE_URL"], poolclass=NullPool)
    try:
        with engine.connect() as conexion:
            conexion.exec_driver_sql("SET TRANSACTION READ ONLY")
            return [tuple(fila) for fila in conexion.execute(text(consulta), parametros)]
    finally:
        engine.dispose()


def capa_bd(informe: Informe) -> None:
    for resultado in verificar_todas():
        informe.anotar("BD", f"Migraciones {resultado.servicio}", resultado.estado == "OK",
                       f"{resultado.estado}: {', '.join(sorted(resultado.actuales)) or '—'}")


def capa_ms(informe: Informe, urls: list[str]) -> None:
    for url in urls:
        for ruta in ("/health", "/health/db"):
            try:
                inicio = time.perf_counter()
                respuesta = httpx.get(f"{url}{ruta}", timeout=30)
                ms = int((time.perf_counter() - inicio) * 1000)
                cuerpo = respuesta.json()
                ok = respuesta.status_code == 200 and cuerpo.get("status") == "ok"
                informe.anotar("MS", f"{url}{ruta}", ok,
                               f"{respuesta.status_code} {cuerpo.get('servicio', '')} ({ms} ms)")
            except httpx.HTTPError as exc:
                informe.anotar("MS", f"{url}{ruta}", False, type(exc).__name__)


def capa_gateway(informe: Informe, gateway: httpx.Client) -> None:
    salud = gateway.get("/api/health/servicios").json()
    for nombre, estado in salud.get("servicios", {}).items():
        informe.anotar("Gateway", f"Ve a {nombre}", estado.get("estado") == "ok",
                       f"{estado.get('estado')} ({estado.get('latencia_ms', '—')} ms)")
    version = gateway.get("/openapi.json").json()["info"]["version"]
    congelado = BACKEND_DIR / "docs" / "openapi" / f"sgtm-gateway-{version}.json"
    informe.anotar("Gateway", "Publica un contrato congelado", congelado.exists(),
                   f"versión {version}")


def capa_web(informe: Informe, web: str, gateway_url: str) -> None:
    try:
        indice = httpx.get(web, timeout=30)
        informe.anotar("Web", "Sirve la aplicación", indice.status_code == 200
                       and 'id="root"' in indice.text, f"{indice.status_code} {web}")
        proxy = httpx.get(f"{web}/api/health", timeout=30)
        informe.anotar("Web", "Su /api llega a la Gateway", proxy.status_code == 200
                       and proxy.json().get("servicio") == "gateway", f"{proxy.status_code}")
    except httpx.HTTPError as exc:
        informe.anotar("Web", "Sirve la aplicación", False, type(exc).__name__)
        return
    origen = web.rstrip("/")
    preflight = httpx.options(f"{gateway_url}/api/auth/login", timeout=30, headers={
        "Origin": origen, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"})
    permitido = preflight.headers.get("access-control-allow-origin") == origen
    informe.anotar("Web", "La Gateway acepta el CORS del origen web", permitido,
                   f"{preflight.status_code} Allow-Origin={preflight.headers.get('access-control-allow-origin')}")


def capa_persistencia(informe: Informe, gateway: httpx.Client) -> None:
    def login(cuenta: tuple[str, str]) -> dict[str, str]:
        respuesta = gateway.post("/api/auth/login", json={"email": cuenta[0], "password": cuenta[1]})
        respuesta.raise_for_status()
        return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}

    cliente, mecanico, admin = login(CLIENTE), login(MECANICO), login(ADMINISTRADOR)

    yo = gateway.get("/api/auth/me", headers=cliente).json()
    filas = _sql("MS1", "SELECT correo FROM usuario WHERE usuario_id = :id", id=yo["id"])
    informe.anotar("Persistencia", "MS1: el usuario del token existe en taller_ms1",
                   filas == [(yo["email"],)], f"usuario_id={yo['id']}")

    patente = "INT" + secrets.token_hex(2).upper()
    vehiculo = gateway.post("/api/vehiculos", headers=cliente, json={
        "patente": patente, "marca": "Kia", "modelo": "Rio", "anio": 2019, "kilometraje": 70000})
    if not informe.anotar("Persistencia", "Gateway → MS2: crear vehículo",
                          vehiculo.status_code == 201, str(vehiculo.status_code)):
        return
    vehiculo_id = vehiculo.json()["vehiculo_id"]
    filas = _sql("MS2", "SELECT patente, marca, modelo, anio, kilometraje FROM vehiculo "
                        "WHERE vehiculo_id = :id", id=vehiculo_id)
    informe.anotar("Persistencia", "MS2: el vehículo está en taller_ms2.vehiculo",
                   filas == [(patente, "Kia", "Rio", 2019, 70000)], f"vehiculo_id={vehiculo_id}")

    orden = gateway.post("/api/ordenes", headers=admin, json={"vehiculo_id": vehiculo_id})
    if not informe.anotar("Persistencia", "Gateway → MS2: crear orden",
                          orden.status_code == 201, str(orden.status_code)):
        return
    orden_id = orden.json()["orden_id"]
    mecanico_id = gateway.get("/api/auth/me", headers=mecanico).json()["id"]
    asignada = gateway.put(f"/api/ordenes/{orden_id}/mecanico", headers=admin,
                           json={"mecanico_id": mecanico_id})
    informe.anotar("Persistencia", "Gateway → MS2 → MS1: asignar mecánico (valida rol en MS1)",
                   asignada.status_code == 200, str(asignada.status_code))
    filas = _sql("MS2", "SELECT estado_codigo, mecanico_actual_id FROM orden_trabajo "
                        "WHERE orden_id = :id", id=orden_id)
    informe.anotar("Persistencia", "MS2: la orden quedó asignada en orden_trabajo",
                   filas == [(2, mecanico_id)], f"orden_id={orden_id} → {filas}")
    historial = _sql("MS2", "SELECT estado_nuevo FROM historial_estado WHERE orden_id = :id "
                            "ORDER BY historial_id", id=orden_id)
    informe.anotar("Persistencia", "MS2: historial_estado registra 1 → 2",
                   [h[0] for h in historial] == [1, 2], str([h[0] for h in historial]))

    subida = gateway.post("/api/evidencias", headers=mecanico,
                          data={"orden_id": str(orden_id), "contexto": "diagnostico"},
                          files={"archivo": ("integracion.jpg", _JPEG, "image/jpeg")})
    if not informe.anotar("Persistencia", "Gateway → MS4 → MS2: subir evidencia",
                          subida.status_code == 201, str(subida.status_code)):
        return
    evidencia_id = subida.json()["evidencia_id"]
    filas = _sql("MS4", "SELECT clave_objeto, tamano_bytes FROM evidencia "
                        "WHERE evidencia_id = :id", id=evidencia_id)
    informe.anotar("Persistencia", "MS4: el metadato está en taller_ms4.evidencia",
                   len(filas) == 1 and filas[0][1] == len(_JPEG), f"{len(_JPEG)} bytes")
    if filas and os.environ.get("MS4_S3_ENDPOINT"):
        import boto3

        s3 = boto3.client(
            "s3", endpoint_url=os.environ["MS4_S3_ENDPOINT"],
            aws_access_key_id=os.environ.get("MS4_S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("MS4_S3_SECRET_KEY"),
            region_name=os.environ.get("MS4_S3_REGION", "us-east-1"),
        )
        objeto = s3.head_object(Bucket=os.environ.get("MS4_S3_BUCKET", "evidencias"),
                                Key=filas[0][0])
        informe.anotar("Persistencia", "MS4: el archivo está en el almacenamiento S3",
                       objeto["ContentLength"] == len(_JPEG), f"{objeto['ContentLength']} bytes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway", default="http://localhost:8000")
    parser.add_argument("--web", default="http://localhost:5173")
    parser.add_argument("--ms", default=",".join(f"http://localhost:800{n}" for n in range(1, 5)))
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()

    informe = Informe()
    gateway = httpx.Client(base_url=args.gateway, timeout=60)
    capa_bd(informe)
    capa_ms(informe, [u.strip() for u in args.ms.split(",") if u.strip()])
    capa_gateway(informe, gateway)
    capa_web(informe, args.web, args.gateway)
    capa_persistencia(informe, gateway)

    texto = informe.markdown("Integración Web → Gateway → Microservicios → ORM/BD")
    print(texto)
    if args.salida:
        args.salida.write_text(texto, encoding="utf-8")
    return 0 if all(fila[2] for fila in informe.filas) else 1


if __name__ == "__main__":
    sys.exit(main())
