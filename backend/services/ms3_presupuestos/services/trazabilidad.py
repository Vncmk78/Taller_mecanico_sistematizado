"""Trazabilidad Repuesto–Proveedor/Distribuidor (MS3, migración 0007_ms3).

Responde, para un repuesto:
- quién lo abastece hoy (y si es distribuidor oficial o genérico);
- qué proveedores lo abastecieron antes y desde cuándo (historial);
- cuántas unidades entregó cada proveedor (ingresos de stock);
- en qué órdenes se reservó o se usó.

Y para un proveedor: qué repuestos abastece o abasteció y cuántas unidades
entregó de cada uno.
"""
from __future__ import annotations

from sqlalchemy import func, or_, select

from services.ms3_presupuestos.models import (
    HistorialProveedorRepuesto,
    MovimientoInventario,
    Proveedor,
    Repuesto,
)
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.schemas.catalogo import (
    CambioProveedor,
    IngresosPorProveedor,
    ProveedorBreve,
    RepuestoAbastecido,
    TrazabilidadProveedor,
    TrazabilidadRepuesto,
    UsoPorOrden,
)
from services.ms3_presupuestos.services import catalogo


def _breve(proveedor: Proveedor) -> ProveedorBreve:
    return ProveedorBreve(proveedor_id=proveedor.proveedor_id, nombre=proveedor.nombre,
                          tipo_distribuidor=proveedor.tipo_distribuidor)


def trazabilidad_repuesto(uow: UnidadDeTrabajo, repuesto_id: int) -> TrazabilidadRepuesto:
    repuesto = uow.repuestos.obtener_o_error(repuesto_id)
    sesion = uow.sesion

    historial = sesion.scalars(
        select(HistorialProveedorRepuesto)
        .where(HistorialProveedorRepuesto.repuesto_id == repuesto_id)
        .order_by(HistorialProveedorRepuesto.fecha_hora, HistorialProveedorRepuesto.historial_id)
    ).all()

    ingresos = sesion.execute(
        select(MovimientoInventario.proveedor_id, func.count(), func.sum(MovimientoInventario.cantidad),
               func.min(MovimientoInventario.fecha_hora), func.max(MovimientoInventario.fecha_hora))
        .where(MovimientoInventario.repuesto_id == repuesto_id,
               MovimientoInventario.tipo == "ingreso")
        .group_by(MovimientoInventario.proveedor_id)
    ).all()
    proveedores = {p.proveedor_id: p for p in sesion.scalars(
        select(Proveedor).where(Proveedor.proveedor_id.in_([f[0] for f in ingresos])))}

    consumido = dict(sesion.execute(
        select(MovimientoInventario.orden_id, func.sum(MovimientoInventario.cantidad))
        .where(MovimientoInventario.repuesto_id == repuesto_id,
               MovimientoInventario.tipo == "consumo")
        .group_by(MovimientoInventario.orden_id)
    ).all())
    reservado = uow.movimientos.comprometido_por_orden(repuesto_id)
    ordenes = sorted(set(consumido) | set(reservado))

    return TrazabilidadRepuesto(
        repuesto=catalogo.a_repuesto(repuesto, catalogo.umbral_general(uow)),
        proveedor_actual=_breve(repuesto.proveedor),
        historial_proveedores=[
            CambioProveedor(
                proveedor_anterior=_breve(h.proveedor_anterior) if h.proveedor_anterior else None,
                proveedor_nuevo=_breve(h.proveedor_nuevo), fecha_hora=h.fecha_hora,
                registrado_por_id=h.registrado_por_id, observacion=h.observacion)
            for h in historial
        ],
        ingresos_por_proveedor=sorted(
            (IngresosPorProveedor(proveedor=_breve(proveedores[pid]), ingresos=n, unidades=int(u),
                                  primer_ingreso=primero, ultimo_ingreso=ultimo)
             for pid, n, u, primero, ultimo in ingresos),
            key=lambda i: i.primer_ingreso,
        ),
        uso_por_orden=[UsoPorOrden(orden_id=o, reservado=reservado.get(o, 0),
                                   consumido=int(consumido.get(o, 0))) for o in ordenes],
    )


def trazabilidad_proveedor(uow: UnidadDeTrabajo, proveedor_id: int) -> TrazabilidadProveedor:
    proveedor = uow.proveedores.obtener_o_error(proveedor_id)
    sesion = uow.sesion

    unidades = dict(sesion.execute(
        select(MovimientoInventario.repuesto_id, func.sum(MovimientoInventario.cantidad))
        .where(MovimientoInventario.proveedor_id == proveedor_id)
        .group_by(MovimientoInventario.repuesto_id)
    ).all())
    en_historial = select(HistorialProveedorRepuesto.repuesto_id).where(or_(
        HistorialProveedorRepuesto.proveedor_nuevo_id == proveedor_id,
        HistorialProveedorRepuesto.proveedor_anterior_id == proveedor_id))
    repuestos = sesion.scalars(
        select(Repuesto).where(or_(Repuesto.proveedor_id == proveedor_id,
                                   Repuesto.repuesto_id.in_(en_historial),
                                   Repuesto.repuesto_id.in_(list(unidades))))
        .order_by(func.lower(Repuesto.nombre), Repuesto.repuesto_id)
    ).all()

    return TrazabilidadProveedor(
        proveedor=_breve(proveedor),
        unidades_ingresadas=int(sum(unidades.values())),
        repuestos=[RepuestoAbastecido(repuesto_id=r.repuesto_id, nombre=r.nombre,
                                      actual=r.proveedor_id == proveedor_id,
                                      unidades_ingresadas=int(unidades.get(r.repuesto_id, 0)))
                   for r in repuestos],
    )
