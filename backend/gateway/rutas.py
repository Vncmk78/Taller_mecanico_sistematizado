"""Configuración de enrutamiento de la API Gateway.

El primer segmento decide el servicio: `/api/{prefijo}/...` se reenvía tal cual
a `{servicio}/{prefijo}/...`. La tabla `RUTAS` fija esa correspondencia.

MS1 (Autenticación) y MS2 (Vehículos y Órdenes) son las rutas iniciales de la
Semana 1; MS3 y MS4 (Presupuestos y Evidencia Multimedia) se conservan desde
el inicio y se verifican en la Semana 4. Convención: MS3 publica bajo sus
prefijos (`presupuestos`, `repuestos`, `proveedores`, `inventario`) y MS4 todo
bajo `evidencias`; ningún servicio publica bajo `/ordenes/...` porque ese
prefijo resuelve a MS2.
"""
from __future__ import annotations

from gateway.config import settings

# Primer segmento de `/api/*` -> URL base del microservicio destino.
RUTAS: dict[str, str] = {
    # MS1 — Autenticación y Usuarios.
    "auth": settings.MS1_URL,
    # MS2 — Vehículos y Órdenes de Trabajo.
    "vehiculos": settings.MS2_URL,
    "vehiculo": settings.MS2_URL,
    "ordenes": settings.MS2_URL,
    "orden": settings.MS2_URL,
    "clientes": settings.MS2_URL,
    "mecanicos": settings.MS2_URL,
    # MS3 — Presupuestos, Repuestos, Proveedores e Inventario (Semana 4).
    "presupuestos": settings.MS3_URL,
    "presupuesto": settings.MS3_URL,
    "repuestos": settings.MS3_URL,
    "proveedores": settings.MS3_URL,
    "inventario": settings.MS3_URL,
    # MS4 — Evidencia Multimedia (Semana 4).
    "evidencias": settings.MS4_URL,
    "evidencia": settings.MS4_URL,
}


def resolver_microservicio(ruta: str) -> str | None:
    """Devuelve la URL base del microservicio para `ruta`, o `None`.

    `ruta` es el camino que queda bajo `/api/`, por ejemplo `"auth/login"`.

    La búsqueda ignora mayúsculas en el primer segmento (`"AUTH/login"` y
    `"auth/login"` resuelven igual); el camino se sigue reenviando tal como
    llegó. Normalizar el caso de la ruta reenviada es una corrección
    pendiente (Semana 9: rutas o respuestas incompatibles).
    """
    primer_segmento = ruta.split("/", 1)[0].lower()
    return RUTAS.get(primer_segmento)