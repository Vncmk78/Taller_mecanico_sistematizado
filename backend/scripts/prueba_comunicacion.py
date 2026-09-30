"""Prueba de comunicación real Gateway ↔ microservicios (Semana 4).

A diferencia de los tests con respx (que simulan a los microservicios), este
script habla con los servicios LEVANTADOS de verdad y verifica el flujo que
usará el frontend: login en MS1 a través de la Gateway y uso del token en MS2.

Requisitos (ver docs/pruebas-comunicacion-gateway.md):
- Gateway en :8000 y MS1..MS4 en :8001..:8004.
- MS1 y MS2 migrados y con los usuarios de scripts/seed_usuarios_prueba.py.
- La misma clave JWT en MS1_, MS2_ y MS4_JWT_SECRET_KEY (.env).

Uso, desde backend/:
    python scripts/prueba_comunicacion.py
    python scripts/prueba_comunicacion.py --gateway http://localhost:8000

Sale con código 0 si todo pasa y 1 si algo falla.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import httpx

CLIENTE = ("cliente@pruebas.cl", "ClientePrueba123!")
ADMINISTRADOR = ("administrador@pruebas.cl", "AdminPrueba123!")

SERVICIOS = {
    "MS1 Autenticación": "http://localhost:8001",
    "MS2 Vehículos/Órdenes": "http://localhost:8002",
    "MS3 Presupuestos": "http://localhost:8003",
    "MS4 Evidencias": "http://localhost:8004",
}

# Claves que expone la Gateway en /api/health/servicios.
MS_HEALTH = ("ms1_auth", "ms2_taller", "ms3_presupuestos", "ms4_evidencias")


@dataclass
class Resultado:
    paso: str
    esperado: str
    obtenido: str
    ok: bool


resultados: list[Resultado] = []


def registrar(paso: str, esperado: str, obtenido: str, ok: bool) -> None:
    resultados.append(Resultado(paso, esperado, obtenido, ok))


def pedir(cliente: httpx.Client, metodo: str, url: str, **kwargs) -> httpx.Response | None:
    """Hace la petición; devuelve None si el servicio no responde."""
    try:
        return cliente.request(metodo, url, **kwargs)
    except httpx.HTTPError:
        return None


def cuerpo(respuesta: httpx.Response | None) -> dict:
    """JSON de la respuesta, o {} si no hay respuesta o no es JSON."""
    if respuesta is None:
        return {}
    try:
        datos = respuesta.json()
    except ValueError:
        return {}
    return datos if isinstance(datos, dict) else {}


def estado(respuesta: httpx.Response | None) -> str:
    return "sin respuesta" if respuesta is None else str(respuesta.status_code)


def login(cliente: httpx.Client, gw: str, credenciales: tuple[str, str]) -> str | None:
    correo, clave = credenciales
    r = pedir(cliente, "POST", f"{gw}/api/auth/login", json={"email": correo, "password": clave})
    ok = r is not None and r.status_code == 200 and "access_token" in cuerpo(r)
    registrar(f"Login {correo} vía Gateway", "200 + access_token", estado(r), ok)
    return cuerpo(r)["access_token"] if ok else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway", default="http://localhost:8000")
    gw = parser.parse_args().gateway.rstrip("/")

    with httpx.Client(timeout=10) as c:
        # 1) Salud de la Gateway y de cada microservicio (directo a su puerto).
        r = pedir(c, "GET", f"{gw}/api/health")
        registrar("Gateway /api/health", "200", estado(r), r is not None and r.status_code == 200)
        for nombre, base in SERVICIOS.items():
            r = pedir(c, "GET", f"{base}/health")
            registrar(f"{nombre} /health", "200", estado(r), r is not None and r.status_code == 200)

        r = pedir(c, "GET", f"{gw}/api/health/servicios")
        cuerpo_health = cuerpo(r)
        ok = (r is not None and r.status_code == 200
              and cuerpo_health.get("status") == "ok"
              and set(cuerpo_health.get("servicios", {})) == set(MS_HEALTH)
              and all(estado.get("estado") == "ok"
                      for estado in cuerpo_health.get("servicios", {}).values()))
        registrar("/api/health/servicios (4 ok)", "200 + 4 ok", estado(r), ok)

        # 2) Autenticación a través de la Gateway (MS1, coordinado con Deris).
        token_cliente = login(c, gw, CLIENTE)
        token_admin = login(c, gw, ADMINISTRADOR)

        r = pedir(c, "POST", f"{gw}/api/auth/login",
                  json={"email": CLIENTE[0], "password": "clave-incorrecta"})
        registrar("Login con contraseña incorrecta", "401", estado(r),
                  r is not None and r.status_code == 401)

        if token_cliente:
            r = pedir(c, "GET", f"{gw}/api/auth/me",
                      headers={"Authorization": f"Bearer {token_cliente}"})
            ok = r is not None and r.status_code == 200 and cuerpo(r).get("email") == CLIENTE[0]
            registrar("/api/auth/me con token del cliente", "200 + email correcto", estado(r), ok)

            # 3) El token emitido por MS1 lo acepta MS2 (clave JWT compartida).
            r = pedir(c, "GET", f"{gw}/api/vehiculos",
                      headers={"Authorization": f"Bearer {token_cliente}"})
            registrar("/api/vehiculos con token de MS1", "200", estado(r),
                      r is not None and r.status_code == 200)

            alterado = token_cliente[:-4] + ("AAAA" if not token_cliente.endswith("AAAA") else "BBBB")
            r = pedir(c, "GET", f"{gw}/api/vehiculos",
                      headers={"Authorization": f"Bearer {alterado}"})
            registrar("/api/vehiculos con token alterado", "401", estado(r),
                      r is not None and r.status_code == 401)

        if token_admin:
            r = pedir(c, "GET", f"{gw}/api/ordenes",
                      headers={"Authorization": f"Bearer {token_admin}"})
            registrar("/api/ordenes con token de administrador", "200", estado(r),
                      r is not None and r.status_code == 200)

        r = pedir(c, "GET", f"{gw}/api/vehiculos")
        registrar("/api/vehiculos sin token", "401", estado(r),
                  r is not None and r.status_code == 401)

        # 4) MS3 y MS4 alcanzables: aún no tienen endpoints (Semana 5), así que
        #    un 404 que viene DEL microservicio prueba que la Gateway llegó.
        for prefijo, nombre in (("presupuestos", "MS3"), ("evidencias", "MS4")):
            r = pedir(c, "GET", f"{gw}/api/{prefijo}")
            ok = r is not None and r.status_code == 404 and "error" not in cuerpo(r)
            registrar(f"/api/{prefijo} llega a {nombre}", "404 del microservicio", estado(r), ok)

        # 5) Prefijo desconocido: 404 de la Gateway con el formato común.
        r = pedir(c, "GET", f"{gw}/api/noexiste")
        ok = (r is not None and r.status_code == 404
              and cuerpo(r).get("error", {}).get("codigo") is not None)
        registrar("/api/noexiste (formato común)", "404 con error.codigo", estado(r), ok)

        # 6) Trazabilidad: toda respuesta de la Gateway trae X-Request-ID.
        r = pedir(c, "GET", f"{gw}/api/health", headers={"X-Request-ID": "prueba-comunicacion-1"})
        ok = r is not None and r.headers.get("x-request-id") == "prueba-comunicacion-1"
        registrar("X-Request-ID se respeta", "misma cabecera", estado(r), ok)

    ancho = max(len(x.paso) for x in resultados)
    print(f"\n{'Paso'.ljust(ancho)}  {'Esperado':<24} {'Obtenido':<14} Resultado")
    print("-" * (ancho + 52))
    for x in resultados:
        print(f"{x.paso.ljust(ancho)}  {x.esperado:<24} {x.obtenido:<14} {'OK' if x.ok else 'FALLA'}")
    fallas = sum(not x.ok for x in resultados)
    print(f"\n{len(resultados) - fallas}/{len(resultados)} pasos correctos.")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
