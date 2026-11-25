"""Regresión: lecturas repetidas al reservar dentro de la aprobación (semana 11).

Al aprobar un presupuesto, la evaluación de disponibilidad y la reserva leían
dos veces, dentro de la MISMA transacción, lo mismo:
  - los repuestos con SELECT ... FOR UPDATE (y, por populate_existing, de
    nuevo sus proveedores con el selectin);
  - lo comprometido por todas las órdenes para esos repuestos.
Las filas ya estaban bloqueadas y nada escribe movimientos entre ambas
lecturas, así que la segunda no podía traer otro resultado. Eran las 13
sentencias repetidas que quedaban en el recorrido E2E de MS3.

Estas pruebas cuentan las sentencias reales y comprueban que el resultado
(reservas, faltantes) no cambió.
"""
from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms3_presupuestos.models import MovimientoInventario
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.services import reservas
from services.ms3_presupuestos.tests import fabricas
from services.ms3_presupuestos.tests.test_consultas_decision import (
    _decidir,
    _item,
    contar_sentencias,
)


def _lecturas(sentencias: list[str]) -> Counter:
    tipos: Counter = Counter()
    for s in sentencias:
        if re.match(r"SELECT repuesto\..* FROM repuesto .*FOR UPDATE", s):
            tipos["bloquear repuestos"] += 1
        elif s.startswith("SELECT movimiento_inventario.repuesto_id, movimiento_inventario.orden_id"):
            tipos["comprometido"] += 1
        elif re.match(r"SELECT proveedor\..* FROM proveedor ", s):
            tipos["select proveedor"] += 1
    return tipos


def test_aprobar_con_stock_bloquea_y_lee_lo_comprometido_una_sola_vez(db: Session) -> None:
    disco = fabricas.nuevo_repuesto(db, stock=10)
    pastilla = fabricas.nuevo_repuesto(db, stock=5)
    presupuesto = fabricas.nuevo_presupuesto(
        db, estado="enviado", items=[_item(disco), _item(pastilla, "3")])
    ids = (disco.repuesto_id, pastilla.repuesto_id)
    db.expire_all()  # como en una petición real: nada precargado

    with contar_sentencias(db) as sentencias:
        resultado = _decidir(db, presupuesto.presupuesto_id)

    tipos = _lecturas(sentencias)
    assert resultado.efecto_en_orden == "en_reparacion"
    assert resultado.repuestos_reservados == {ids[0]: 2, ids[1]: 3}
    assert tipos["bloquear repuestos"] == 1, tipos
    assert tipos["comprometido"] == 1, tipos
    # Antes 4. Quedan las del presupuesto cargado, la del FOR UPDATE (populate_existing
    # refresca la fila bloqueada y su selectin) y la del detalle de respuesta.
    assert tipos["select proveedor"] <= 3, tipos
    compromisos = db.scalars(select(MovimientoInventario).where(
        MovimientoInventario.orden_id == presupuesto.orden_id,
        MovimientoInventario.tipo == "compromiso")).all()
    assert sorted((m.repuesto_id, m.cantidad) for m in compromisos) == [(ids[0], 2), (ids[1], 3)]


def test_aprobar_sin_stock_informa_faltantes_y_no_reserva(db: Session) -> None:
    escaso = fabricas.nuevo_repuesto(db, stock=1)
    presupuesto = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(escaso, "4")])
    escaso_id = escaso.repuesto_id
    db.expire_all()

    with contar_sentencias(db) as sentencias:
        resultado = _decidir(db, presupuesto.presupuesto_id)

    tipos = _lecturas(sentencias)
    assert resultado.efecto_en_orden == "esperando_repuestos"
    assert [(f.repuesto_id, f.disponible) for f in resultado.repuestos_faltantes] == [(escaso_id, 1)]
    assert resultado.repuestos_reservados == {}
    assert tipos["bloquear repuestos"] == 1, tipos
    assert tipos["comprometido"] == 1, tipos


def test_lo_comprometido_por_otra_orden_se_sigue_descontando(db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=5)
    otra_orden = fabricas.nuevo_orden_id()
    fabricas.nuevo_movimiento(db, repuesto, tipo="compromiso", cantidad=4, orden_id=otra_orden)
    presupuesto = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(repuesto, "2")])
    db.expire_all()

    resultado = _decidir(db, presupuesto.presupuesto_id)

    assert resultado.efecto_en_orden == "esperando_repuestos"
    assert [f.disponible for f in resultado.repuestos_faltantes] == [1]


def test_ajustar_reserva_sin_datos_previos_sigue_funcionando(db: Session) -> None:
    """La firma pública no cambia: sin repuestos ni compromisos previos los lee ella."""
    repuesto = fabricas.nuevo_repuesto(db, stock=3)
    orden_id = fabricas.nuevo_orden_id()
    uow = UnidadDeTrabajo(db)

    faltantes, movimientos = reservas.ajustar_reserva(
        uow, orden_id, {repuesto.repuesto_id: 2}, usuario_id=1)

    assert faltantes == []
    assert [(m.tipo, m.cantidad) for m in movimientos] == [("compromiso", 2)]
