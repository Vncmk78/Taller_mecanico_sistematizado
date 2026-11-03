"""Contratos que necesita la aplicación móvil de Taller de Integración IV.

La app móvil (Integra IV) atiende a dos de los tres roles del sistema: el
Cliente (sigue sus vehículos, órdenes, evidencias y decide presupuestos) y el
Mecánico (atiende sus órdenes asignadas, registra bitácora y sube evidencias).
El Administrador trabaja desde el frontend web y queda fuera de este catálogo.

Este módulo es la lista **cerrada** de operaciones de la Gateway que la app
móvil necesita, con lo que cada una debe garantizar en el OpenAPI publicado.
La consume `tests/test_contratos_integracion_iv.py`, que valida cada entrada
contra `/openapi.json` y contra el OpenAPI real del microservicio dueño.

Reglas para mantenerlo:

* Solo entran rutas publicadas por la Gateway bajo `/api`. Una ruta que la app
  necesite y no exista se anota en `docs/contratos-integracion-iv.md`
  (sección «Fuera del contrato»), nunca aquí.
* `roles` son los roles móviles que la usan; `roles_rechazados` los roles que
  reciben `403` por rol (obliga a publicar el `403`).
* `estados_requeridos` son estados que la app debe manejar explícitamente
  además de los que se derivan solos (401, 404, 422, 502, 504).
"""
from __future__ import annotations

from dataclasses import dataclass

CLIENTE = "cliente"
MECANICO = "mecanico"


@dataclass(frozen=True)
class OperacionMovil:
    """Una operación de la Gateway que consume la app móvil."""

    metodo: str
    ruta: str
    flujo: str
    roles: tuple[str, ...]
    publica: bool = False
    roles_rechazados: tuple[str, ...] = ()
    estados_requeridos: tuple[str, ...] = ()

    @property
    def clave(self) -> str:
        return f"{self.metodo.upper()} {self.ruta}"


OPERACIONES_INTEGRACION_IV: tuple[OperacionMovil, ...] = (
    # ── Acceso (ambos roles) ────────────────────────────────────────────
    OperacionMovil(
        "post", "/api/auth/register", "Acceso", (CLIENTE,), publica=True,
        estados_requeridos=("409", "422"),
    ),
    OperacionMovil(
        "post", "/api/auth/login", "Acceso", (CLIENTE, MECANICO), publica=True,
        # 403: cuenta sin roles; 429: bloqueo temporal por intentos fallidos.
        estados_requeridos=("401", "403", "422", "429"),
    ),
    OperacionMovil("get", "/api/auth/me", "Acceso", (CLIENTE, MECANICO)),
    # ── Vehículos del cliente ───────────────────────────────────────────
    OperacionMovil(
        "get", "/api/vehiculos", "Vehículos", (CLIENTE,),
        roles_rechazados=(MECANICO,),
    ),
    OperacionMovil(
        "post", "/api/vehiculos", "Vehículos", (CLIENTE,),
        roles_rechazados=(MECANICO,), estados_requeridos=("409",),
    ),
    # Cliente: el propio. Mecánico: solo los de sus órdenes asignadas (si no, 404).
    OperacionMovil(
        "get", "/api/vehiculos/{vehiculo_id}", "Vehículos", (CLIENTE, MECANICO),
    ),
    OperacionMovil(
        "patch", "/api/vehiculos/{vehiculo_id}", "Vehículos", (CLIENTE,),
        roles_rechazados=(MECANICO,),
    ),
    OperacionMovil(
        "get", "/api/vehiculos/asignados", "Vehículos", (MECANICO,),
        roles_rechazados=(CLIENTE,),
    ),
    # ── Seguimiento de órdenes (ambos roles, visibilidad por rol) ──────
    OperacionMovil("get", "/api/ordenes", "Órdenes", (CLIENTE, MECANICO)),
    OperacionMovil("get", "/api/ordenes/{orden_id}", "Órdenes", (CLIENTE, MECANICO)),
    OperacionMovil(
        "get", "/api/ordenes/{orden_id}/historial", "Órdenes", (CLIENTE, MECANICO),
    ),
    OperacionMovil(
        "post", "/api/ordenes/{orden_id}/cancelacion", "Órdenes", (CLIENTE,),
        roles_rechazados=(MECANICO,), estados_requeridos=("409",),
    ),
    # ── Trabajo del mecánico ────────────────────────────────────────────
    OperacionMovil(
        "patch", "/api/ordenes/{orden_id}/estado", "Trabajo del mecánico",
        (MECANICO,), roles_rechazados=(CLIENTE,), estados_requeridos=("409",),
    ),
    OperacionMovil(
        "get", "/api/ordenes/{orden_id}/bitacora", "Trabajo del mecánico",
        (CLIENTE, MECANICO),
    ),
    OperacionMovil(
        "post", "/api/ordenes/{orden_id}/bitacora", "Trabajo del mecánico",
        (MECANICO,), roles_rechazados=(CLIENTE,),
    ),
    # ── Evidencias ──────────────────────────────────────────────────────
    OperacionMovil(
        "post", "/api/evidencias", "Evidencias", (MECANICO,),
        roles_rechazados=(CLIENTE,), estados_requeridos=("413", "415"),
    ),
    OperacionMovil("get", "/api/evidencias", "Evidencias", (CLIENTE, MECANICO)),
    OperacionMovil(
        "get", "/api/evidencias/{evidencia_id}", "Evidencias", (CLIENTE, MECANICO),
    ),
    OperacionMovil(
        "get", "/api/evidencias/{evidencia_id}/descarga", "Evidencias",
        (CLIENTE, MECANICO),
    ),
    # ── Presupuestos (el cliente decide) ────────────────────────────────
    OperacionMovil("get", "/api/presupuestos", "Presupuestos", (CLIENTE, MECANICO)),
    OperacionMovil(
        "get", "/api/presupuestos/{presupuesto_id}", "Presupuestos",
        (CLIENTE, MECANICO),
    ),
    OperacionMovil(
        "get", "/api/presupuestos/{presupuesto_id}/versiones/{numero}",
        "Presupuestos", (CLIENTE, MECANICO),
    ),
    OperacionMovil(
        "post", "/api/presupuestos/{presupuesto_id}/versiones/{numero}/decision",
        "Presupuestos", (CLIENTE,), roles_rechazados=(MECANICO,),
        # 503: decisión guardada con aplicación pendiente en MS2 (reintentable).
        estados_requeridos=("409", "503"),
    ),
    OperacionMovil(
        "get", "/api/presupuestos/decisiones/{decision_id}", "Presupuestos",
        (CLIENTE,), roles_rechazados=(MECANICO,),
    ),
    OperacionMovil(
        "post", "/api/presupuestos/decisiones/{decision_id}/aplicacion",
        "Presupuestos", (CLIENTE,), roles_rechazados=(MECANICO,),
        estados_requeridos=("409", "503"),
    ),
)
