"""Smoke tests de todos los prefijos de la API Gateway (Semana 7).

Recorre, contra una Gateway LEVANTADA (local o desplegada), cada prefijo que
enruta el catálogo `gateway.rutas.MICROSERVICIOS` y comprueba que la petición
llega al microservicio correcto y vuelve con el formato esperado. No crea ni
modifica datos: solo hace `GET` (y, si se le pasan credenciales, un login).

Qué verifica:

1. `GET /api/health` responde 200.
2. `GET /api/health/servicios` responde 200 con los cuatro servicios en `ok`.
3. `GET /api/health/servicios/{servicio}` (diagnóstico, Semana 7) de cada uno;
   si la Gateway desplegada aún no lo tiene, se marca OMITIDO.
4. Cada prefijo publicado, SIN token: un endpoint protegido representativo
   debe responder 401 DEL microservicio (cuerpo `{"detail": ...}`, nunca un
   error de la Gateway como 502/503/504 o RUTA_NO_ENCONTRADA).
5. Cada alias heredado: llega al microservicio (su 404, no el de la Gateway).
6. Un prefijo inexistente: 404 RUTA_NO_ENCONTRADA de la Gateway.
7. Toda respuesta devuelve el `X-Request-ID` enviado.
8. Opcional (`--email/--password`): login vía Gateway y el mismo endpoint
   representativo de cada prefijo CON token: debe responder el microservicio
   (200, 403, 404 o 422 según el rol), nunca un error de disponibilidad.

Uso, desde backend/:
    python scripts/smoke_prefijos_gateway.py
    python scripts/smoke_prefijos_gateway.py --gateway https://tallerconect.vercel.app
    python scripts/smoke_prefijos_gateway.py --email admin@pruebas.cl --password ...
    python scripts/smoke_prefijos_gateway.py --json resultados.json

Sale con código 0 si todo lo aplicable pasa y 1 si algo falla.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gateway.rutas import MICROSERVICIOS  # noqa: E402  (requiere backend/ en el path)

PASA = "PASA"
FALLA = "FALLA"
OMITIDO = "OMITIDO"

# Endpoint protegido representativo de cada prefijo publicado (GET, sin efectos).
REPRESENTATIVOS: dict[str, str] = {
    "auth": "/auth/me",
    "notificaciones": "/notificaciones",
    "vehiculos": "/vehiculos",
    "ordenes": "/ordenes",
    "presupuestos": "/presupuestos",
    "repuestos": "/repuestos",
    "proveedores": "/proveedores",
    "inventario": "/inventario/alertas",
    "evidencias": "/evidencias?orden_id=1",
}

# Códigos que solo genera la Gateway: si aparecen, la petición no llegó bien.
CODIGOS_GATEWAY = {
    "RUTA_NO_ENCONTRADA",
    "METODO_NO_PERMITIDO",
    "MICROSERVICIO_INALCANZABLE",
    "TIEMPO_AGOTADO",
    "GATEWAY_SATURADA",
    "ERROR_MICROSERVICIO",
    "ERROR_INTERNO",
}


@dataclass
class Resultado:
    prueba: str
    servicio: str
    esperado: str
    obtenido: str
    estado: str


def _cuerpo(respuesta: httpx.Response | None) -> dict:
    if respuesta is None:
        return {}
    try:
        datos = respuesta.json()
    except ValueError:
        return {}
    return datos if isinstance(datos, dict) else {}


def codigo_gateway(respuesta: httpx.Response | None) -> str | None:
    """Código del formato común si la respuesta la generó la Gateway, si no None."""
    error = _cuerpo(respuesta).get("error")
    if isinstance(error, dict) and error.get("codigo") in CODIGOS_GATEWAY:
        return error["codigo"]
    return None


def _obtenido(respuesta: httpx.Response | None) -> str:
    if respuesta is None:
        return "sin respuesta"
    codigo = codigo_gateway(respuesta)
    return f"{respuesta.status_code} {codigo}" if codigo else str(respuesta.status_code)


def _pedir(
    cliente: httpx.Client, metodo: str, url: str, request_id: str, **kwargs
) -> httpx.Response | None:
    cabeceras = {"X-Request-ID": request_id, **kwargs.pop("headers", {})}
    try:
        return cliente.request(metodo, url, headers=cabeceras, **kwargs)
    except httpx.HTTPError:
        return None


def _id_ok(respuesta: httpx.Response | None, request_id: str) -> bool:
    return respuesta is not None and respuesta.headers.get("x-request-id") == request_id


def ejecutar(
    cliente: httpx.Client,
    base: str = "",
    *,
    email: str | None = None,
    password: str | None = None,
) -> list[Resultado]:
    """Ejecuta los smoke tests con `cliente` contra la Gateway en `base`.

    `cliente` puede ser un `httpx.Client` real o el `TestClient` de FastAPI
    (los tests lo usan en proceso, con `base=""`).
    """
    base = base.rstrip("/")
    resultados: list[Resultado] = []

    def anotar(prueba: str, servicio: str, esperado: str, respuesta, ok: bool, rid: str) -> None:
        ok = ok and _id_ok(respuesta, rid)
        resultados.append(
            Resultado(prueba, servicio, esperado, _obtenido(respuesta), PASA if ok else FALLA)
        )

    # 1) Salud de la Gateway.
    rid = "smoke-health"
    r = _pedir(cliente, "GET", f"{base}/api/health", rid)
    anotar("GET /api/health", "gateway", "200", r, r is not None and r.status_code == 200, rid)

    # 2) Salud agregada.
    rid = "smoke-health-servicios"
    r = _pedir(cliente, "GET", f"{base}/api/health/servicios", rid)
    servicios = _cuerpo(r).get("servicios", {})
    ok = (
        r is not None
        and r.status_code == 200
        and set(servicios) == {s.nombre for s in MICROSERVICIOS}
        and all(e.get("estado") == "ok" for e in servicios.values())
    )
    anotar("GET /api/health/servicios", "los cuatro", "200 y 4 en ok", r, ok, rid)

    # 3) Diagnóstico por servicio.
    for servicio in MICROSERVICIOS:
        rid = f"smoke-diag-{servicio.nombre.replace('_', '-')}"
        r = _pedir(cliente, "GET", f"{base}/api/health/servicios/{servicio.nombre}", rid)
        if r is not None and codigo_gateway(r) == "RUTA_NO_ENCONTRADA":
            resultados.append(Resultado(
                f"GET /api/health/servicios/{servicio.nombre}", servicio.nombre,
                "200 estado ok", "Gateway sin diagnóstico (anterior a Semana 7)", OMITIDO,
            ))
            continue
        ok = r is not None and r.status_code == 200 and _cuerpo(r).get("estado") == "ok"
        anotar(f"GET /api/health/servicios/{servicio.nombre}", servicio.nombre,
               "200 estado ok", r, ok, rid)

    # 4) y 5) Cada prefijo, sin token.
    for servicio in MICROSERVICIOS:
        for prefijo in servicio.prefijos:
            ruta = REPRESENTATIVOS[prefijo]
            rid = f"smoke-{prefijo}"
            r = _pedir(cliente, "GET", f"{base}/api{ruta}", rid)
            ok = (
                r is not None
                and r.status_code == 401
                and codigo_gateway(r) is None
                and "detail" in _cuerpo(r)
            )
            anotar(f"GET /api{ruta} sin token", servicio.nombre,
                   "401 del microservicio", r, ok, rid)
        for alias in servicio.alias:
            rid = f"smoke-alias-{alias}"
            r = _pedir(cliente, "GET", f"{base}/api/{alias}", rid)
            ok = r is not None and r.status_code == 404 and codigo_gateway(r) is None
            anotar(f"GET /api/{alias} (alias)", servicio.nombre,
                   "404 del microservicio", r, ok, rid)

    # 6) Prefijo inexistente.
    rid = "smoke-no-existe"
    r = _pedir(cliente, "GET", f"{base}/api/prefijo-inexistente", rid)
    ok = r is not None and r.status_code == 404 and codigo_gateway(r) == "RUTA_NO_ENCONTRADA"
    anotar("GET /api/prefijo-inexistente", "gateway", "404 RUTA_NO_ENCONTRADA", r, ok, rid)

    # 8) Con token (opcional).
    if email and password:
        rid = "smoke-login"
        r = _pedir(cliente, "POST", f"{base}/api/auth/login", rid,
                   json={"email": email, "password": password})
        token = _cuerpo(r).get("access_token")
        anotar("POST /api/auth/login", "ms1_auth", "200 con access_token", r,
               r is not None and r.status_code == 200 and bool(token), rid)
        if token:
            for servicio in MICROSERVICIOS:
                for prefijo in servicio.prefijos:
                    ruta = REPRESENTATIVOS[prefijo]
                    rid = f"smoke-token-{prefijo}"
                    r = _pedir(cliente, "GET", f"{base}/api{ruta}", rid,
                               headers={"Authorization": f"Bearer {token}"})
                    ok = (
                        r is not None
                        and r.status_code in {200, 403, 404, 422}
                        and codigo_gateway(r) is None
                    )
                    anotar(f"GET /api{ruta} con token", servicio.nombre,
                           "200/403/404/422 del microservicio", r, ok, rid)
    return resultados


def imprimir(resultados: list[Resultado]) -> None:
    ancho = max(len(r.prueba) for r in resultados)
    for r in resultados:
        print(f"[{r.estado:7}] {r.prueba:<{ancho}}  {r.servicio:<16} "
              f"esperado: {r.esperado:<34} obtenido: {r.obtenido}")
    total = len(resultados)
    fallas = sum(r.estado == FALLA for r in resultados)
    omitidos = sum(r.estado == OMITIDO for r in resultados)
    print(f"\n{total - fallas - omitidos} pasan, {fallas} fallan, {omitidos} omitidos de {total}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway", default="http://localhost:8000")
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--json", type=Path, help="Guarda los resultados en un archivo JSON")
    args = parser.parse_args()

    with httpx.Client(timeout=args.timeout) as cliente:
        resultados = ejecutar(cliente, args.gateway, email=args.email, password=args.password)
    imprimir(resultados)
    if args.json:
        args.json.write_text(
            json.dumps([asdict(r) for r in resultados], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 1 if any(r.estado == FALLA for r in resultados) else 0


if __name__ == "__main__":
    raise SystemExit(main())
