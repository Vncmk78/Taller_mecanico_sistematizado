"""Datos semilla de INTEGRACIÓN de MS3: proveedores, repuestos y existencias.

Complementan el catálogo mínimo de `datos_prueba.py` (que siguen usando las
pruebas unitarias) con un catálogo más amplio para que el frontend, la app
móvil y los demás microservicios prueben contra datos realistas que cubren
todos los casos de inventario:

    caso                                   repuesto de ejemplo
    -------------------------------------  ---------------------------------
    stock holgado                          Aceite sintético 5W-30 (litro)
    sin stock (alerta)                     Líquido de frenos DOT4 (500 ml)
    bajo el umbral particular (alerta)     Alternador reacondicionado
    bajo el umbral general (alerta)        Kit de embrague
    justo en el umbral (NO es alerta)      Bujía de iridio
    unidades comprometidas para una orden  Amortiguador delantero
    stock corregido con un ajuste          Filtro de aire
    búsqueda con tildes y eñes             Importadora Ñuble / Bujía
    proveedor sin repuestos                Neumáticos Cautín

Las EXISTENCIAS no se escriben a mano: cada repuesto declara la secuencia de
movimientos (ingreso, ajuste, compromiso, consumo, liberación) que explica su
stock. La semilla los registra con las mismas reglas que la API, así el stock
siempre coincide con el historial de movimientos.

Las órdenes son REFERENCIAS LÓGICAS a MS2 (§8). Se nombran por su papel y el
script de semilla decide qué orden_id real usar (por defecto las órdenes 1 y
2 de la semilla de MS2).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from services.ms3_presupuestos import datos_prueba

TipoMovimiento = Literal["ingreso", "ajuste", "compromiso", "consumo", "liberacion"]
PapelOrden = Literal["en_reparacion", "recibida"]

# Papel de cada orden → orden_id de MS2 que se usa por defecto.
ORDENES_POR_DEFECTO: dict[PapelOrden, int] = {
    "en_reparacion": 1,  # orden con diagnóstico, ya consume repuestos
    "recibida": 2,       # orden recién ingresada, solo tiene repuestos reservados
}


@dataclass(frozen=True)
class MovimientoDato:
    tipo: TipoMovimiento
    cantidad: int
    orden: PapelOrden | None = None


@dataclass(frozen=True)
class RepuestoIntegracion:
    nombre: str
    movimientos: tuple[MovimientoDato, ...]
    umbral_particular: int | None = None

    @property
    def stock_esperado(self) -> int:
        """Stock físico: ingresos + ajustes − consumos."""
        signo = {"ingreso": 1, "ajuste": 1, "consumo": -1}
        return sum(signo.get(m.tipo, 0) * m.cantidad for m in self.movimientos)

    def comprometido_esperado(self) -> dict[PapelOrden, int]:
        """Unidades reservadas por orden: compromisos − liberaciones − consumos (mín. 0)."""
        neto: dict[PapelOrden, int] = {}
        for m in self.movimientos:
            if m.orden is None:
                continue
            delta = m.cantidad if m.tipo == "compromiso" else -m.cantidad
            neto[m.orden] = max(0, neto.get(m.orden, 0) + delta)
        return {orden: c for orden, c in neto.items() if c > 0}


@dataclass(frozen=True)
class ProveedorIntegracion:
    nombre: str
    contacto: str
    repuestos: tuple[RepuestoIntegracion, ...] = ()


def _ingreso(n: int) -> MovimientoDato:
    return MovimientoDato("ingreso", n)


CATALOGO_INTEGRACION: tuple[ProveedorIntegracion, ...] = (
    ProveedorIntegracion(
        "Lubricantes Araucanía",
        "pedidos@lubricantesaraucania.cl / +56 45 274 1100",
        (
            RepuestoIntegracion("Aceite sintético 5W-30 (litro)", (_ingreso(40),)),
            RepuestoIntegracion("Refrigerante concentrado (galón)", (_ingreso(18),)),
            # Se usaron las 2 unidades en la orden en reparación: queda en 0.
            RepuestoIntegracion("Líquido de frenos DOT4 (500 ml)", (
                _ingreso(2), MovimientoDato("consumo", 2, "en_reparacion"),
            ), umbral_particular=3),
        ),
    ),
    ProveedorIntegracion(
        "Electro Auto Sur",
        "contacto@electroautosur.cl / +56 9 7123 4567",
        (
            RepuestoIntegracion("Batería 12V 60Ah", (_ingreso(3),), umbral_particular=2),
            # 5 = umbral general: está justo en el límite y NO genera alerta.
            RepuestoIntegracion("Bujía de iridio", (_ingreso(5),)),
            RepuestoIntegracion("Alternador reacondicionado", (_ingreso(1),), umbral_particular=2),
        ),
    ),
    ProveedorIntegracion(
        "Suspensiones Pérez",
        "ventas@suspensionesperez.cl / +56 41 223 9876",
        (
            # Reserva 3, libera 1: quedan 2 comprometidas → disponible 6 − 2 = 4.
            RepuestoIntegracion("Amortiguador delantero", (
                _ingreso(6),
                MovimientoDato("compromiso", 3, "recibida"),
                MovimientoDato("liberacion", 1, "recibida"),
            )),
            # 4 − 1 = 3 < umbral general 5 → alerta.
            RepuestoIntegracion("Kit de embrague", (
                _ingreso(4), MovimientoDato("consumo", 1, "en_reparacion"),
            )),
            RepuestoIntegracion("Rótula de suspensión", (_ingreso(8),), umbral_particular=2),
        ),
    ),
    ProveedorIntegracion(
        "Importadora Ñuble",
        "importaciones@nuble.cl / +56 42 243 5500",
        (
            RepuestoIntegracion("Correa de distribución", (_ingreso(7),)),
            # Se contaron 12, en el inventario físico había 10: ajuste −2.
            RepuestoIntegracion("Filtro de aire", (
                _ingreso(12), MovimientoDato("ajuste", -2),
            )),
            RepuestoIntegracion("Bomba de agua", (_ingreso(4),), umbral_particular=1),
        ),
    ),
    # Sin repuestos: para probar el filtro con_repuestos=false y que se puede eliminar.
    ProveedorIntegracion("Neumáticos Cautín", "neumaticos@cautin.cl / +56 45 231 0101"),
)


def repuestos_integracion() -> dict[str, RepuestoIntegracion]:
    return {r.nombre: r for p in CATALOGO_INTEGRACION for r in p.repuestos}


def validar_catalogo() -> list[str]:
    """Problemas del catálogo antes de cargarlo (vacío = está bien).

    Comprueba lo mismo que exigirá la base y la API: nombres únicos, que ningún
    movimiento deje stock negativo, que no se reserve más de lo disponible y
    que no se libere más de lo reservado.
    """
    problemas: list[str] = []
    minimos = {p.nombre.lower() for p in datos_prueba.CATALOGO}
    nombres_prov = [p.nombre.lower() for p in CATALOGO_INTEGRACION]
    if len(set(nombres_prov)) != len(nombres_prov) or minimos & set(nombres_prov):
        problemas.append("Hay nombres de proveedor repetidos")
    minimos_rep = {r.nombre.lower() for p in datos_prueba.CATALOGO for r in p.repuestos}
    nombres_rep = [r.nombre.lower() for p in CATALOGO_INTEGRACION for r in p.repuestos]
    if len(set(nombres_rep)) != len(nombres_rep) or minimos_rep & set(nombres_rep):
        problemas.append("Hay nombres de repuesto repetidos")

    for repuesto in repuestos_integracion().values():
        stock, reservado = 0, {}
        for i, m in enumerate(repuesto.movimientos, start=1):
            con_orden = m.tipo in ("compromiso", "consumo", "liberacion")
            if con_orden != (m.orden is not None) or (m.cantidad <= 0 and m.tipo != "ajuste"):
                problemas.append(f"{repuesto.nombre}: movimiento {i} mal formado")
                continue
            propio = reservado.get(m.orden, 0)
            otros = sum(reservado.values()) - propio
            if m.tipo in ("ingreso", "ajuste"):
                stock += m.cantidad
            elif m.tipo == "compromiso":
                if m.cantidad > stock - sum(reservado.values()):
                    problemas.append(f"{repuesto.nombre}: movimiento {i} reserva más de lo disponible")
                reservado[m.orden] = propio + m.cantidad
            elif m.tipo == "consumo":
                if m.cantidad > stock - otros:
                    problemas.append(f"{repuesto.nombre}: movimiento {i} consume más de lo disponible")
                stock -= m.cantidad
                reservado[m.orden] = max(0, propio - m.cantidad)
            else:
                if m.cantidad > propio:
                    problemas.append(f"{repuesto.nombre}: movimiento {i} libera más de lo reservado")
                reservado[m.orden] = propio - m.cantidad
            if stock < 0:
                problemas.append(f"{repuesto.nombre}: movimiento {i} deja stock negativo")
    return problemas
