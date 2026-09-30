"""Datos mínimos de MS3: la ÚNICA fuente de los datos de prueba del servicio.

Los usan:
- `scripts/seed_datos_ms3.py`, que los carga en una base real (local o Neon).
- Las fixtures de `services/ms3_presupuestos/tests/`, que los recrean dentro de
  cada prueba y los descartan al final.

Si cambia el catálogo de prueba, se cambia aquí y ambos quedan alineados.

Los ids de usuarios son REFERENCIAS LÓGICAS a MS1 (§8) y coinciden con las
cuentas de `scripts/seed_usuarios_prueba.py`:
cliente = 1, mecánico = 2, administrador = 3.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# ------------------------------------------------------------------ usuarios --
CLIENTE_ID = 1
MECANICO_ID = 2
ADMIN_ID = 3

# ---------------------------------------------------------------- inventario --
UMBRAL_GENERAL = 5


@dataclass(frozen=True)
class RepuestoDato:
    nombre: str
    stock: int
    umbral_particular: int | None = None


@dataclass(frozen=True)
class ProveedorDato:
    nombre: str
    contacto: str
    repuestos: tuple[RepuestoDato, ...]


CATALOGO: tuple[ProveedorDato, ...] = (
    ProveedorDato(
        "Frenos del Sur",
        "contacto@frenosdelsur.cl / +56 9 8765 4321",
        (
            RepuestoDato("Pastillas de freno delanteras", stock=10, umbral_particular=4),
            # Bajo su umbral (2 < 3): sirve para probar alertas de stock.
            RepuestoDato("Disco de freno delantero", stock=2, umbral_particular=3),
        ),
    ),
    ProveedorDato(
        "Repuestos Temuco",
        "ventas@repuestostemuco.cl / +56 45 221 0000",
        (
            RepuestoDato("Filtro de aceite", stock=15),
            RepuestoDato("Aceite 10W-40 (litro)", stock=24),
        ),
    ),
)

REPUESTO_BAJO_UMBRAL = "Disco de freno delantero"

# --------------------------------------------------------------- presupuesto --


@dataclass(frozen=True)
class ItemDato:
    tipo: str  # "repuesto" | "mano_de_obra"
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    repuesto: str | None = None  # nombre del repuesto del CATALOGO


ITEMS_PRESUPUESTO_EJEMPLO: tuple[ItemDato, ...] = (
    ItemDato("repuesto", "Juego de pastillas de freno delanteras",
             Decimal("1"), Decimal("38990"), repuesto="Pastillas de freno delanteras"),
    ItemDato("mano_de_obra", "Cambio de pastillas y revision de frenos",
             Decimal("1.5"), Decimal("20000")),
)
TOTAL_PRESUPUESTO_EJEMPLO = Decimal("68990")
