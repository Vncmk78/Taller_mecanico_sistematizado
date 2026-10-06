"""Casos de uso iniciales de presupuestos (Semana 5).

- crear_presupuesto: presupuesto lógico de una orden + versión 1 en borrador.
- listar_presupuestos / obtener_presupuesto / obtener_version: consultas.
- reemplazar_items: edita los ítems de una versión mientras es borrador.

Cada escritura es UNA transacción (`with uow.transaccion()`). Las reglas de
versionado las garantiza la base (triggers 0003_ms3); aquí se anticipan para
responder 409/422 con mensajes claros.

Enviar al cliente, registrar la decisión y crear nuevas versiones son las
operaciones transaccionales de la tarea siguiente.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal

from services.ms3_presupuestos.models import (
    ItemPresupuesto,
    Presupuesto,
    VersionPresupuesto,
)
from services.ms3_presupuestos.persistencia import (
    ConflictoDeDatos,
    ReglaDeDatosViolada,
    UnidadDeTrabajo,
)
from services.ms3_presupuestos.schemas.presupuesto import (
    DecisionSalida,
    ItemEntrada,
    ItemSalida,
    PresupuestoDetalle,
    PresupuestoResumen,
    VersionDetalle,
)


# ---------------------------------------------------------------- escritura --

def crear_presupuesto(
    uow: UnidadDeTrabajo, *, orden_id: int, items: Sequence[ItemEntrada], creado_por_id: int
) -> Presupuesto:
    """Crea el único presupuesto de la orden con su versión 1 (borrador)."""
    with uow.transaccion():
        if uow.presupuestos.de_orden(orden_id) is not None:
            raise ConflictoDeDatos(
                f"La orden {orden_id} ya tiene presupuesto; las correcciones se "
                "registran como una nueva versión"
            )
        version = VersionPresupuesto(numero=1, creado_por_id=creado_por_id)
        version.items = _construir_items(uow, items)
        presupuesto = Presupuesto(orden_id=orden_id)
        presupuesto.versiones.append(version)
        uow.presupuestos.agregar(presupuesto)
    return presupuesto


def reemplazar_items(
    uow: UnidadDeTrabajo, *, presupuesto_id: int, numero: int, items: Sequence[ItemEntrada]
) -> VersionPresupuesto:
    """Reemplaza todos los ítems de una versión que sigue en borrador."""
    with uow.transaccion():
        uow.presupuestos.obtener_o_error(presupuesto_id)
        version = uow.presupuestos.version(presupuesto_id, numero)
        if not version.editable:
            raise ConflictoDeDatos(
                f"La versión {numero} ya fue enviada y no se puede modificar; "
                "las correcciones se registran como una nueva versión"
            )
        version.items.clear()
        uow.sesion.flush()  # borra los ítems anteriores antes de insertar
        version.items.extend(_construir_items(uow, items))
        uow.sesion.flush()
    return version


def _construir_items(uow: UnidadDeTrabajo, items: Iterable[ItemEntrada]) -> list[ItemPresupuesto]:
    construidos = []
    for item in items:
        repuesto = None
        if item.repuesto_id is not None:
            repuesto = uow.repuestos.obtener(item.repuesto_id)
            if repuesto is None:
                raise ReglaDeDatosViolada(f"El repuesto {item.repuesto_id} no existe")
        construidos.append(ItemPresupuesto(
            tipo=item.tipo, descripcion=item.descripcion, cantidad=item.cantidad,
            precio_unitario=item.precio_unitario, repuesto=repuesto,
        ))
    return construidos


# ----------------------------------------------------------------- lectura --

def listar_presupuestos(
    uow: UnidadDeTrabajo, *, orden_id: int | None, desde: int, limite: int
) -> tuple[int, Sequence[Presupuesto]]:
    total = uow.presupuestos.contar_busqueda(orden_id=orden_id)
    return total, uow.presupuestos.buscar(orden_id=orden_id, desde=desde, limite=limite)


def obtener_presupuesto(uow: UnidadDeTrabajo, presupuesto_id: int) -> Presupuesto:
    return uow.presupuestos.obtener_o_error(presupuesto_id)


def obtener_version(uow: UnidadDeTrabajo, presupuesto_id: int, numero: int) -> VersionPresupuesto:
    uow.presupuestos.obtener_o_error(presupuesto_id)
    return uow.presupuestos.version(presupuesto_id, numero)


# ---------------------------------------------------- ORM → contrato HTTP --

def estado_version(version: VersionPresupuesto) -> str:
    if version.decision is not None:
        return "aprobada" if version.decision.decision == "aprobado" else "rechazada"
    return "enviada" if version.enviada else "borrador"


CENTAVOS = Decimal("0.01")


def _dos_decimales(valor: Decimal) -> Decimal:
    """Misma escala siempre (recién creado o leído de la base): 68990.00."""
    return Decimal(valor).quantize(CENTAVOS)


def total_version(version: VersionPresupuesto) -> Decimal:
    return _dos_decimales(sum((i.subtotal for i in version.items), Decimal("0")))


def a_version_detalle(version: VersionPresupuesto) -> VersionDetalle:
    return VersionDetalle(
        numero=version.numero,
        estado=estado_version(version),
        es_modificacion=version.es_modificacion,
        creado_por_id=version.creado_por_id,
        creado_en=version.creado_en,
        enviado_en=version.enviado_en,
        bloqueada_en=version.bloqueada_en,
        total=total_version(version),
        items=[_a_item(i) for i in sorted(version.items, key=lambda i: i.item_id)],
        decision=DecisionSalida.model_validate(version.decision) if version.decision else None,
    )


def _a_item(item: ItemPresupuesto) -> ItemSalida:
    repuesto = item.repuesto
    return ItemSalida(
        item_id=item.item_id, tipo=item.tipo, descripcion=item.descripcion,
        cantidad=_dos_decimales(item.cantidad),
        precio_unitario=_dos_decimales(item.precio_unitario),
        subtotal=_dos_decimales(item.subtotal), repuesto_id=item.repuesto_id,
        repuesto_nombre=repuesto.nombre if repuesto else None,
        proveedor_nombre=repuesto.proveedor.nombre if repuesto else None,
    )


def _datos_resumen(presupuesto: Presupuesto) -> dict:
    ultima = presupuesto.versiones[-1]
    vigente = presupuesto.version_vigente
    return {
        "presupuesto_id": presupuesto.presupuesto_id,
        "orden_id": presupuesto.orden_id,
        "creado_en": presupuesto.creado_en,
        "cantidad_versiones": len(presupuesto.versiones),
        "ultima_version": ultima.numero,
        "estado_ultima_version": estado_version(ultima),
        "total_ultima_version": total_version(ultima),
        "version_vigente": vigente.numero if vigente else None,
    }


def a_resumen(presupuesto: Presupuesto) -> PresupuestoResumen:
    return PresupuestoResumen(**_datos_resumen(presupuesto))


def a_detalle(presupuesto: Presupuesto) -> PresupuestoDetalle:
    return PresupuestoDetalle(
        **_datos_resumen(presupuesto),
        versiones=[a_version_detalle(v) for v in presupuesto.versiones],
    )
