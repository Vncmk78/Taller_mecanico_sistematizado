"""Configuración de enrutamiento de la API Gateway.

El primer segmento decide el servicio: `/api/{prefijo}/...` se reenvía tal cual
a `{servicio}/{prefijo}/...`. El catálogo `MICROSERVICIOS` es la única fuente
de verdad del direccionamiento: de él salen la tabla `RUTAS` que usa el proxy,
el health check de servicios y el índice `/` de la Gateway.

Cada microservicio declara:

* `prefijos`: los que publica de verdad (sus `APIRouter(prefix=...)`). Todo
  endpoint del servicio cuelga de uno de ellos (lo verifica
  `tests/test_gateway_direccionamiento.py` contra los apps reales).
* `alias`: prefijos históricos que se conservan para no romper clientes; se
  reenvían al mismo servicio y, si este no los publica, responde su propio 404.

Convención (Semana 4): MS3 publica bajo `presupuestos`, `repuestos`,
`proveedores` e `inventario`, y MS4 todo bajo `evidencias`; ningún servicio
publica bajo un prefijo de otro (por ejemplo, nada fuera de MS2 cuelga de
`/ordenes/...`).
"""
from __future__ import annotations

from dataclasses import dataclass

from gateway.config import settings


@dataclass(frozen=True)
class Microservicio:
    """Un microservicio detrás de la Gateway y los prefijos que atiende."""

    # Nombre público (se usa en health checks y logs; nunca la URL interna).
    nombre: str
    # Descripción corta para el índice de la Gateway.
    descripcion: str
    # URL base interna (env GATEWAY_MS<n>_URL).
    url: str
    # Prefijos que el servicio publica en sus routers.
    prefijos: tuple[str, ...]
    # Prefijos heredados que se reenvían igual al servicio.
    alias: tuple[str, ...] = ()

    @property
    def todos_los_prefijos(self) -> tuple[str, ...]:
        return self.prefijos + self.alias


MICROSERVICIOS: tuple[Microservicio, ...] = (
    Microservicio(
        nombre="ms1_auth",
        descripcion="Autenticación y Usuarios",
        url=settings.MS1_URL,
        prefijos=("auth",),
    ),
    Microservicio(
        nombre="ms2_taller",
        descripcion="Vehículos y Órdenes de Trabajo",
        url=settings.MS2_URL,
        prefijos=("vehiculos", "ordenes"),
        alias=("vehiculo", "orden", "clientes", "mecanicos"),
    ),
    Microservicio(
        nombre="ms3_presupuestos",
        descripcion="Presupuestos, Repuestos, Proveedores e Inventario",
        url=settings.MS3_URL,
        prefijos=("presupuestos", "repuestos", "proveedores", "inventario"),
        alias=("presupuesto",),
    ),
    Microservicio(
        nombre="ms4_evidencias",
        descripcion="Evidencia Multimedia",
        url=settings.MS4_URL,
        prefijos=("evidencias",),
        alias=("evidencia",),
    ),
)

# Nombre público -> microservicio.
MICROSERVICIOS_POR_NOMBRE: dict[str, Microservicio] = {
    servicio.nombre: servicio for servicio in MICROSERVICIOS
}


def _construir_rutas() -> dict[str, str]:
    """Primer segmento de `/api/*` -> URL base del servicio destino.

    Falla al importar si un prefijo quedara asignado a dos servicios: el
    direccionamiento sería ambiguo y dependería del orden del catálogo.
    """
    rutas: dict[str, str] = {}
    duenos: dict[str, str] = {}
    for servicio in MICROSERVICIOS:
        for prefijo in servicio.todos_los_prefijos:
            if prefijo in duenos:
                raise ValueError(
                    f"Prefijo '{prefijo}' asignado a {duenos[prefijo]} y {servicio.nombre}"
                )
            duenos[prefijo] = servicio.nombre
            rutas[prefijo] = servicio.url
    return rutas


# Primer segmento de `/api/*` -> URL base del microservicio destino. Se conserva
# como diccionario mutable porque los tests lo parchean con `monkeypatch.setitem`.
RUTAS: dict[str, str] = _construir_rutas()

# Primer segmento -> nombre público del servicio (para logs y timeouts).
_SERVICIO_POR_PREFIJO: dict[str, str] = {
    prefijo: servicio.nombre
    for servicio in MICROSERVICIOS
    for prefijo in servicio.todos_los_prefijos
}


def primer_segmento(ruta: str) -> str:
    """Primer segmento de `ruta` en minúsculas (`"AUTH/login"` -> `"auth"`)."""
    return ruta.split("/", 1)[0].lower()


def resolver_microservicio(ruta: str) -> str | None:
    """Devuelve la URL base del microservicio para `ruta`, o `None`.

    `ruta` es el camino que queda bajo `/api/`, por ejemplo `"auth/login"`.

    La búsqueda ignora mayúsculas en el primer segmento (`"AUTH/login"` y
    `"auth/login"` resuelven igual); el camino se sigue reenviando tal como
    llegó. Normalizar el caso de la ruta reenviada es una corrección
    pendiente (Semana 9: rutas o respuestas incompatibles).
    """
    return RUTAS.get(primer_segmento(ruta))


def nombre_servicio(ruta: str) -> str | None:
    """Nombre público del microservicio que atiende `ruta`, o `None`."""
    return _SERVICIO_POR_PREFIJO.get(primer_segmento(ruta))


def prefijos_publicos(servicio: Microservicio) -> list[str]:
    """Prefijos `/api/*` del servicio (publicados y alias), ordenados."""
    return sorted(f"/api/{prefijo}" for prefijo in servicio.todos_los_prefijos)
