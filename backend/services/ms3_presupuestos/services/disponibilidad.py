"""Validación de disponibilidad de stock antes de utilizar un repuesto (§4.6).

Antes de usar un repuesto en una orden (consumirlo, reservarlo o aprobar un
presupuesto que lo incluye) se responde una sola pregunta: ¿alcanza el stock
para esta orden sin tomar unidades reservadas por otra?

    disponible para la orden = stock − lo comprometido por OTRAS órdenes

Lo que la propia orden ya reservó cuenta como disponible para ella. Sin orden,
solo cuenta lo libre (stock − todo lo comprometido).

Las cantidades de un presupuesto son decimales (p. ej. 1,5 litros); el stock
se mide en unidades enteras, así que lo requerido se redondea hacia arriba
(1,5 litros → 2 unidades).

Con `bloquear=True` los repuestos se leen con SELECT ... FOR UPDATE, todos en
orden de id: la respuesta sigue siendo cierta hasta que termine la transacción
que la pidió (la usa la aprobación del presupuesto para no aprobar dos órdenes
contra las mismas unidades).
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import Decimal

from sqlalchemy import func, select

from services.ms3_presupuestos.models import MovimientoInventario, Repuesto, VersionPresupuesto
from services.ms3_presupuestos.persistencia import (
    ConflictoDeDatos,
    RecursoNoEncontrado,
    UnidadDeTrabajo,
)
from services.ms3_presupuestos.schemas.inventario import (
    DisponibilidadRepuesto,
    ItemRequerido,
    ResultadoDisponibilidad,
)


def unidades(cantidad: Decimal | int) -> int:
    """Cantidad presupuestada → unidades enteras de stock (redondeo hacia arriba)."""
    return math.ceil(Decimal(cantidad))


def requeridos_de_items(items: Iterable[ItemRequerido]) -> dict[int, int]:
    """Suma las cantidades por repuesto (un repuesto repetido se acumula)."""
    total: dict[int, int] = defaultdict(int)
    for item in items:
        total[item.repuesto_id] += item.cantidad
    return dict(total)


def requeridos_de_version(version: VersionPresupuesto) -> dict[int, int]:
    """Unidades de cada repuesto que pide una versión del presupuesto."""
    total: dict[int, Decimal] = defaultdict(Decimal)
    for item in version.items:
        if item.repuesto_id is not None:
            total[item.repuesto_id] += item.cantidad
    return {rid: unidades(c) for rid, c in total.items()}


def evaluar_repuesto(
    uow: UnidadDeTrabajo, repuesto: Repuesto, requerido: int, orden_id: int | None,
    compromisos: dict[int, int] | None = None,
) -> DisponibilidadRepuesto:
    if compromisos is None:
        compromisos = uow.movimientos.comprometido_por_orden(repuesto.repuesto_id)
    propio = compromisos.get(orden_id, 0) if orden_id is not None else 0
    de_otras = sum(compromisos.values()) - propio
    disponible = repuesto.stock - de_otras
    return DisponibilidadRepuesto(
        repuesto_id=repuesto.repuesto_id, nombre=repuesto.nombre,
        proveedor_nombre=repuesto.proveedor.nombre, requerido=requerido,
        stock=repuesto.stock, reservado_para_orden=propio,
        comprometido_otras_ordenes=de_otras, disponible=disponible,
        alcanza=requerido <= disponible, faltan=max(0, requerido - disponible),
    )


def evaluar(
    uow: UnidadDeTrabajo,
    requeridos: Mapping[int, int],
    *,
    orden_id: int | None = None,
    bloquear: bool = False,
) -> ResultadoDisponibilidad:
    """Disponibilidad de cada repuesto requerido (404 si alguno no existe)."""
    if bloquear:
        repuestos = uow.repuestos.bloquear_varios(requeridos)
    else:
        repuestos = {
            r.repuesto_id: r for r in uow.sesion.scalars(
                select(Repuesto).where(Repuesto.repuesto_id.in_(list(requeridos))))
        }
    inexistentes = sorted(set(requeridos) - set(repuestos))
    if inexistentes:
        raise RecursoNoEncontrado(
            "No existen los repuestos: " + ", ".join(str(i) for i in inexistentes))
    # Una sola consulta para lo comprometido de todos los repuestos.
    compromisos = uow.movimientos.comprometido_por_ordenes(requeridos)
    detalle = [evaluar_repuesto(uow, repuestos[rid], cantidad, orden_id, compromisos.get(rid, {}))
               for rid, cantidad in sorted(requeridos.items())]
    return ResultadoDisponibilidad(
        orden_id=orden_id, disponible=all(d.alcanza for d in detalle), repuestos=detalle)


def consumido_por_orden(uow: UnidadDeTrabajo, orden_id: int) -> dict[int, int]:
    """Unidades ya consumidas por la orden, por repuesto."""
    filas = uow.sesion.execute(
        select(MovimientoInventario.repuesto_id, func.sum(MovimientoInventario.cantidad))
        .where(MovimientoInventario.orden_id == orden_id,
               MovimientoInventario.tipo == "consumo")
        .group_by(MovimientoInventario.repuesto_id)
    ).all()
    return {rid: int(total) for rid, total in filas}


def version_aprobada_de_orden(uow: UnidadDeTrabajo, orden_id: int) -> VersionPresupuesto:
    presupuesto = uow.presupuestos.de_orden(orden_id)
    if presupuesto is None:
        raise RecursoNoEncontrado(f"La orden {orden_id} no tiene presupuesto")
    vigente = presupuesto.version_vigente
    if vigente is None:
        raise ConflictoDeDatos(f"La orden {orden_id} no tiene un presupuesto aprobado")
    return vigente


def pendientes_de_orden(uow: UnidadDeTrabajo, orden_id: int) -> tuple[VersionPresupuesto, dict[int, int]]:
    """Lo que falta usar del presupuesto aprobado: requerido − ya consumido."""
    vigente = version_aprobada_de_orden(uow, orden_id)
    consumido = consumido_por_orden(uow, orden_id)
    pendientes = {
        rid: max(0, cantidad - consumido.get(rid, 0))
        for rid, cantidad in requeridos_de_version(vigente).items()
    }
    return vigente, pendientes


def evaluar_orden(uow: UnidadDeTrabajo, orden_id: int) -> ResultadoDisponibilidad:
    """¿Alcanza el stock para terminar el trabajo aprobado de la orden?"""
    vigente, pendientes = pendientes_de_orden(uow, orden_id)
    resultado = evaluar(uow, pendientes, orden_id=orden_id) if pendientes else \
        ResultadoDisponibilidad(orden_id=orden_id, disponible=True, repuestos=[])
    resultado.presupuesto_id = vigente.presupuesto_id
    resultado.version = vigente.numero
    return resultado
