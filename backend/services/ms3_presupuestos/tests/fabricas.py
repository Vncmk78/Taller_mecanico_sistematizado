"""Fábricas de objetos de prueba de MS3 (patrón "test data builder").

Cada función crea lo MÍNIMO válido para que la base lo acepte, hace flush (la
base valida al tiro y el objeto recibe su id) y permite sobrescribir solo lo
que a la prueba le importa:

    repuesto = nuevo_repuesto(db, stock=0)
    presupuesto = nuevo_presupuesto(db, estado="aprobado")

Los nombres y orden_id se generan ÚNICOS por llamada, así las pruebas no
chocan entre sí ni con datos que ya existan en la base (semilla, Neon).
Nada se confirma: las pruebas corren dentro de la transacción de la fixture
`db`, que se revierte al terminar.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.models import (
    DecisionPresupuesto,
    ItemPresupuesto,
    MovimientoInventario,
    ParametroInventario,
    Presupuesto,
    Proveedor,
    Repuesto,
    VersionPresupuesto,
)

_secuencia = count(1)
# orden_id de prueba en un rango alto para no chocar con órdenes reales de MS2.
_ordenes = count(9_000_001)

ESTADOS_PRESUPUESTO = ("borrador", "enviado", "aprobado", "rechazado")

# (sufijo, stock, umbral_particular) por defecto para nuevo_proveedor().
REPUESTOS_POR_DEFECTO: tuple[tuple[str, int, int | None], ...] = (
    ("disco", 1, 3),      # bajo su umbral
    ("filtro", 50, None),  # usa el umbral general
)


def _unico(base: str) -> str:
    return f"{base} #{next(_secuencia)}"


def nuevo_orden_id() -> int:
    return next(_ordenes)


# ---------------------------------------------------------------- catálogo --

def nuevo_proveedor(
    db: Session,
    nombre: str | None = None,
    *,
    contacto: str = "pruebas@taller.cl",
    repuestos: Iterable[tuple[str, int, int | None]] = REPUESTOS_POR_DEFECTO,
) -> Proveedor:
    """Proveedor con repuestos llamados '<nombre> <sufijo>' (en orden)."""
    nombre = nombre or _unico("Proveedor")
    proveedor = Proveedor(nombre=nombre, contacto=contacto)
    proveedor.repuestos += [
        Repuesto(nombre=f"{nombre} {sufijo}", stock=stock, umbral_particular=umbral)
        for sufijo, stock, umbral in repuestos
    ]
    db.add(proveedor)
    db.flush()
    return proveedor


def nuevo_repuesto(
    db: Session,
    nombre: str | None = None,
    *,
    stock: int = 10,
    umbral_particular: int | None = None,
    proveedor: Proveedor | None = None,
) -> Repuesto:
    proveedor = proveedor or nuevo_proveedor(db, repuestos=())
    repuesto = Repuesto(proveedor=proveedor, nombre=nombre or _unico("Repuesto"),
                        stock=stock, umbral_particular=umbral_particular)
    db.add(repuesto)
    db.flush()
    return repuesto


def cargar_catalogo(db: Session) -> dict[str, Repuesto]:
    """Carga el catálogo mínimo de datos_prueba.CATALOGO.

    Devuelve {nombre original del repuesto: Repuesto}. A cada nombre se le
    agrega un sufijo único para no chocar con la semilla si ya está cargada.
    Crea además el movimiento de ingreso inicial de cada repuesto.
    """
    sufijo = f"#{next(_secuencia)}"
    repuestos: dict[str, Repuesto] = {}
    for prov in datos.CATALOGO:
        proveedor = Proveedor(nombre=f"{prov.nombre} {sufijo}", contacto=prov.contacto)
        for r in prov.repuestos:
            repuesto = Repuesto(nombre=f"{r.nombre} {sufijo}", stock=r.stock,
                                umbral_particular=r.umbral_particular)
            proveedor.repuestos.append(repuesto)
            repuestos[r.nombre] = repuesto
        db.add(proveedor)
    db.flush()
    for repuesto in repuestos.values():
        nuevo_movimiento(db, repuesto, tipo="ingreso", cantidad=repuesto.stock)
    return repuestos


# -------------------------------------------------------------- inventario --

def nuevo_movimiento(
    db: Session,
    repuesto: Repuesto,
    *,
    tipo: str = "ingreso",
    cantidad: int = 1,
    orden_id: int | None = None,
    clave_operacion: str | None = None,
    registrado_por_id: int = datos.MECANICO_ID,
) -> MovimientoInventario:
    """Movimiento válido. Si el tipo exige orden y no se da, se genera una."""
    if orden_id is None and tipo in ("compromiso", "consumo", "liberacion"):
        orden_id = nuevo_orden_id()
    movimiento = MovimientoInventario(
        clave_operacion=clave_operacion or _unico("op"), repuesto=repuesto,
        orden_id=orden_id, tipo=tipo, cantidad=cantidad,
        registrado_por_id=registrado_por_id,
    )
    db.add(movimiento)
    db.flush()
    return movimiento


def umbral_general_vigente(db: Session, valor: int = datos.UMBRAL_GENERAL) -> ParametroInventario:
    """Deja UN umbral general vigente con `valor` (cierra el que hubiera)."""
    for vigente in db.scalars(
        select(ParametroInventario).where(ParametroInventario.vigente_hasta.is_(None))
    ):
        vigente.vigente_hasta = datetime.now(timezone.utc) + timedelta(seconds=1)
    db.flush()
    parametro = ParametroInventario(umbral_general=valor, actualizado_por_id=datos.ADMIN_ID)
    db.add(parametro)
    db.flush()
    return parametro


# -------------------------------------------------------------- presupuesto --

def nueva_version(
    db: Session,
    orden_id: int | None = None,
    *,
    items: Iterable[ItemPresupuesto] | None = None,
) -> VersionPresupuesto:
    """Presupuesto nuevo con su versión 1 en BORRADOR.

    Sin `items`, agrega un ítem de mano de obra de $20.000.
    """
    presupuesto = Presupuesto(orden_id=orden_id or nuevo_orden_id())
    version = VersionPresupuesto(numero=1, creado_por_id=datos.MECANICO_ID)
    version.items += list(items) if items is not None else [
        ItemPresupuesto(tipo="mano_de_obra", descripcion="Revision",
                        cantidad=Decimal("1"), precio_unitario=Decimal("20000"))
    ]
    presupuesto.versiones.append(version)
    db.add(presupuesto)
    db.flush()
    return version


def nueva_version_siguiente(
    db: Session, presupuesto: Presupuesto, *, items: Iterable[ItemPresupuesto] | None = None
) -> VersionPresupuesto:
    """Versión número siguiente en BORRADOR; es_modificacion si ya hubo aprobación."""
    version = VersionPresupuesto(
        numero=presupuesto.siguiente_numero, creado_por_id=datos.MECANICO_ID,
        es_modificacion=presupuesto.version_vigente is not None,
    )
    version.items += list(items) if items is not None else [
        ItemPresupuesto(tipo="mano_de_obra", descripcion="Trabajo adicional",
                        cantidad=Decimal("1"), precio_unitario=Decimal("15000"))
    ]
    presupuesto.versiones.append(version)
    db.flush()
    return version


def enviar(db: Session, version: VersionPresupuesto) -> VersionPresupuesto:
    """Marca la versión como enviada (desde aquí queda congelada por trigger).

    Dentro de la transacción de prueba now() es constante: se envía en el mismo
    instante de creación para que una decisión posterior (now()) sea válida.
    """
    db.refresh(version)
    version.enviado_en = version.creado_en
    db.flush()
    return version


def decidir(
    db: Session,
    version: VersionPresupuesto,
    decision: str,
    motivo: str | None = None,
) -> DecisionPresupuesto:
    """Registra la decisión del cliente; aprobar bloquea la versión (trigger)."""
    if decision == "rechazado" and motivo is None:
        motivo = "Rechazado en prueba"
    registro = DecisionPresupuesto(version_id=version.version_id,
                                   cliente_usuario_id=datos.CLIENTE_ID,
                                   decision=decision, motivo=motivo)
    db.add(registro)
    db.flush()
    db.refresh(version)
    return registro


def nuevo_presupuesto(
    db: Session,
    *,
    estado: str = "borrador",
    orden_id: int | None = None,
    items: Iterable[ItemPresupuesto] | None = None,
) -> Presupuesto:
    """Presupuesto con su versión 1 en el estado pedido (borrador/enviado/aprobado/rechazado)."""
    if estado not in ESTADOS_PRESUPUESTO:
        raise ValueError(f"estado debe ser uno de {ESTADOS_PRESUPUESTO}")
    version = nueva_version(db, orden_id, items=items)
    if estado != "borrador":
        enviar(db, version)
    if estado in ("aprobado", "rechazado"):
        decidir(db, version, "aprobado" if estado == "aprobado" else "rechazado")
    return version.presupuesto


def items_de_ejemplo(repuestos: dict[str, Repuesto]) -> list[ItemPresupuesto]:
    """Ítems de datos_prueba.ITEMS_PRESUPUESTO_EJEMPLO, enlazados al catálogo cargado."""
    return [
        ItemPresupuesto(tipo=i.tipo, descripcion=i.descripcion, cantidad=i.cantidad,
                        precio_unitario=i.precio_unitario,
                        repuesto=repuestos[i.repuesto] if i.repuesto else None)
        for i in datos.ITEMS_PRESUPUESTO_EJEMPLO
    ]
