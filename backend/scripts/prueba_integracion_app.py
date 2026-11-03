"""Prueba HTTP de consulta por rol, sin crear ni modificar datos de negocio.

Solo hace GET y POST /api/auth/login (el login puede registrar auditoría).
Requiere cuentas de prueba de un solo rol; no usa contraseñas predeterminadas.
Lee GATEWAY_URL y APP_TEST_{CLIENTE,MECANICO,ADMINISTRADOR}_{EMAIL,PASSWORD}
desde backend/.env o el proceso. --salida guarda OpenAPI y muestras anonimizadas
en un directorio local nuevo, fuera de Git. Nunca exporta JWT ni /auth/me.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROLES = ("cliente", "mecanico", "administrador")
CAMPOS_ORDEN = {
    "orden_id", "vehiculo_id", "ingreso_id", "estado_codigo",
    "mecanico_actual_id", "creado_por_id", "creado_en", "actualizado_en",
}
CAMPOS_VEHICULO = {"vehiculo_id", "cliente_id", "patente", "marca", "modelo", "anio", "kilometraje"}
CAMPOS_PRIVADOS = {"email", "full_name", "patente", "observacion", "nombre", "telefono"}


def anonimizar(valor: object) -> object:
    if isinstance(valor, dict):
        return {
            clave: "[omitido]" if clave in CAMPOS_PRIVADOS and dato is not None else anonimizar(dato)
            for clave, dato in valor.items()
            if clave not in {"access_token", "password", "authorization"}
        }
    if isinstance(valor, list):
        return [anonimizar(dato) for dato in valor[:1]]
    return valor


def validar_url(url: str) -> str:
    partes = urlsplit(url)
    local = partes.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not partes.hostname or partes.username or partes.password or partes.query or partes.fragment
        or partes.path not in {"", "/"}
        or (partes.scheme != "https" and not (partes.scheme == "http" and local))
    ):
        raise ValueError("GATEWAY_URL debe ser un origen HTTPS (HTTP solo en localhost), sin /api")
    return url.rstrip("/")


class PruebaIntegracion:
    def __init__(self, cliente: httpx.Client) -> None:
        self.cliente = cliente
        self.fallos = 0
        self.omitidas = 0
        self.muestras: list[dict] = []

    def comprobar(self, condicion: bool, nombre: str) -> bool:
        print(f"{'OK' if condicion else 'FALLA'}: {nombre}")
        self.fallos += int(not condicion)
        return condicion

    def consultar(self, ruta: str, codigo: int, rol: str = "sin token", token: str | None = None) -> object:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        nombre = f"{rol}: GET {ruta}"
        try:
            respuesta = self.cliente.get(ruta, headers=headers)
            if not self.comprobar(respuesta.status_code == codigo, f"{nombre} → {respuesta.status_code} (esperado {codigo})"):
                return None
            if codigo == 401:
                self.comprobar(respuesta.headers.get("www-authenticate", "").lower() == "bearer", f"{nombre}: desafío Bearer")
            datos = respuesta.json()
            if ruta not in {"/api/auth/me", "/openapi.json"}:
                self.muestras.append({"rol": rol, "metodo": "GET", "ruta": ruta, "status": codigo, "body": anonimizar(datos)})
            return datos
        except (httpx.HTTPError, ValueError) as exc:
            self.comprobar(False, f"{nombre}: error de transporte/JSON ({type(exc).__name__})")
            return None

    def probar_rol(self, rol: str, email: str, password: str) -> None:
        try:
            respuesta = self.cliente.post("/api/auth/login", json={"email": email, "password": password})
            if not self.comprobar(respuesta.status_code == 200, f"{rol}: login → {respuesta.status_code}"):
                return
            datos = respuesta.json()
            token = datos.get("access_token") if isinstance(datos, dict) else None
            if not self.comprobar(isinstance(token, str) and bool(token), f"{rol}: JWT recibido"):
                return
        except (httpx.HTTPError, ValueError) as exc:
            self.comprobar(False, f"{rol}: login no disponible ({type(exc).__name__})")
            return

        usuario = self.consultar("/api/auth/me", 200, rol, token)
        if not self.comprobar(isinstance(usuario, dict) and usuario.get("roles") == [rol] and usuario.get("is_active") is True, f"{rol}: cuenta activa con un único rol"):
            return

        self.consultar("/api/vehiculos", 403 if rol == "mecanico" else 200, rol, token)
        self.consultar("/api/vehiculos/asignados", 200 if rol == "mecanico" else 403, rol, token)
        ordenes = self.consultar("/api/ordenes", 200, rol, token)
        if not self.comprobar(isinstance(ordenes, list), f"{rol}: listado de órdenes es una lista"):
            return
        if not ordenes:
            self.omitidas += 1
            print(f"OMITIDO: {rol}: detalle, historial, vehículo y evidencias; no hay órdenes visibles")
            return
        orden = ordenes[0]
        if not self.comprobar(isinstance(orden, dict) and CAMPOS_ORDEN <= orden.keys(), f"{rol}: campos de OrdenRespuesta"):
            return
        orden_id, vehiculo_id = orden["orden_id"], orden["vehiculo_id"]
        if not self.comprobar(type(orden_id) is int and orden_id > 0 and type(vehiculo_id) is int and vehiculo_id > 0, f"{rol}: identificadores positivos"):
            return
        detalle = self.consultar(f"/api/ordenes/{orden_id}", 200, rol, token)
        self.comprobar(isinstance(detalle, dict) and CAMPOS_ORDEN <= detalle.keys() and detalle.get("orden_id") == orden_id, f"{rol}: detalle de la orden visible")
        historial = self.consultar(f"/api/ordenes/{orden_id}/historial", 200, rol, token)
        self.comprobar(isinstance(historial, list), f"{rol}: historial es una lista")
        vehiculo = self.consultar(f"/api/vehiculos/{vehiculo_id}", 200, rol, token)
        self.comprobar(isinstance(vehiculo, dict) and CAMPOS_VEHICULO <= vehiculo.keys() and vehiculo.get("vehiculo_id") == vehiculo_id, f"{rol}: vehículo de la orden visible")
        evidencias = self.consultar(f"/api/evidencias?orden_id={orden_id}", 200, rol, token)
        self.comprobar(isinstance(evidencias, list), f"{rol}: evidencias es una lista")


def main() -> int:
    entorno = {**dotenv_values(BACKEND_DIR / ".env"), **os.environ}
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway", default=entorno.get("GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--salida", type=Path, help="Directorio NUEVO para openapi.json y muestras.json anonimizadas")
    args = parser.parse_args()
    try:
        url = validar_url(args.gateway)
    except ValueError as exc:
        parser.error(str(exc))
    if args.salida and args.salida.exists():
        parser.error("El directorio de salida ya existe; elige uno nuevo")
    credenciales: dict[str, tuple[str, str]] = {}
    for rol in ROLES:
        prefijo = f"APP_TEST_{rol.upper()}"
        email, password = entorno.get(f"{prefijo}_EMAIL"), entorno.get(f"{prefijo}_PASSWORD")
        if not email or not password:
            parser.error(f"Define {prefijo}_EMAIL y {prefijo}_PASSWORD en el entorno o backend/.env")
        credenciales[rol] = (email, password)

    with httpx.Client(base_url=url, timeout=15, follow_redirects=False) as cliente:
        prueba = PruebaIntegracion(cliente)
        prueba.consultar("/api/health", 200)
        spec = prueba.consultar("/openapi.json", 200)
        prueba.comprobar(isinstance(spec, dict) and "openapi" in spec and "/api/ordenes" in spec.get("paths", {}), "OpenAPI publica órdenes")
        for ruta in ("/api/auth/me", "/api/vehiculos", "/api/ordenes"):
            prueba.consultar(ruta, 401)
        for rol, (email, password) in credenciales.items():
            prueba.probar_rol(rol, email, password)

    if args.salida:
        args.salida.mkdir(parents=True, mode=0o700)
        for nombre, datos in (("openapi.json", spec), ("muestras.json", {
            "anonimizadas": True, "fallos": prueba.fallos, "omitidas": prueba.omitidas,
            "respuestas": prueba.muestras,
        })):
            archivo = args.salida / nombre
            archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            archivo.chmod(0o600)
    print(f"Resultado: {prueba.fallos} fallos; {prueba.omitidas} grupos de consultas omitidos.")
    print("Esta prueba no verifica escrituras, aislamiento entre cuentas ni transferencias S3.")
    return 1 if prueba.fallos else 2 if prueba.omitidas else 0


if __name__ == "__main__":
    raise SystemExit(main())
