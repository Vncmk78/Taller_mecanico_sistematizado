"""Regresión: consultas duplicadas al decidir un presupuesto (semana 11).

En el ambiente de integración, el registro de PostgreSQL mostró que aprobar
un presupuesto repetía dentro de la MISMA transacción:
  - la versión con sus decisiones, ítems, repuestos y proveedores (3 veces):
    al cargar el presupuesto, al pedir la versión aparte y al refrescarla
    entera para leer `bloqueada_en`;
  - lo ya consumido por la orden (2 veces): `_pendientes` se calculaba dos veces.
Estas pruebas cuentan las sentencias reales enviadas a PostgreSQL para que
esas repeticiones no vuelvan, y comprueban que el resultado no cambió.
"""
from __future__ import annotations

import re
from collections import Counter
from contextlib import contextmanager
from decimal import Decimal
from typing import Iterator

from sqlalchemy import event
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.models import ItemPresupuesto, Repuesto
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.services import presupuestos as casos
from services.ms3_presupuestos.tests import fabricas


@contextmanager
def contar_sentencias(db: Session) -> Iterator[list[str]]:
    sentencias: list[str] = []

    def registrar(_conn, _cursor, sentencia, *_args) -> None:
        sentencias.append(re.sub(r"\s+", " ", sentencia).strip())

    conexion = db.connection()
    event.listen(conexion, "before_cursor_execute", registrar)
    try:
        yield sentencias
    finally:
        event.remove(conexion, "before_cursor_execute", registrar)


def _tipo(sentencia: str) -> str:
    """Clasifica una sentencia por la tabla principal que lee o escribe."""
    if sentencia.startswith("SELECT"):
        if "sum(movimiento_inventario.cantidad)" in sentencia:
            return "consumido_por_orden"
        columna = re.match(r"SELECT version_presupuesto\.(\w+) FROM version_presupuesto", sentencia)
        if columna:  # refresh de una sola columna escrita por el servidor
            return f"releer {columna.group(1)}"
        tabla = re.search(r"\bFROM (\w+)", sentencia)
        return f"select {tabla.group(1) if tabla else '?'}"
    return sentencia.split(" ", 1)[0].lower()


def _item(repuesto: Repuesto, cantidad: str = "2") -> ItemPresupuesto:
    return ItemPresupuesto(tipo="repuesto", descripcion=repuesto.nombre, cantidad=Decimal(cantidad),
                           precio_unitario=Decimal("1000"), repuesto=repuesto)


def _decidir(db: Session, presupuesto_id: int, decision: str = "aprobado"):
    return casos.decidir_version(
        UnidadDeTrabajo(db), presupuesto_id=presupuesto_id, numero=1,
        cliente_usuario_id=datos.CLIENTE_ID, decision=decision,
        motivo="Prefiero otro taller" if decision == "rechazado" else None,
        confirmar_cancelacion=decision == "rechazado")


def test_aprobar_no_repite_lecturas_de_version_ni_de_consumo(db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=10)
    presupuesto_id = fabricas.nuevo_presupuesto(
        db, estado="enviado", items=[_item(repuesto)]).presupuesto_id
    repuesto_id = repuesto.repuesto_id
    db.expire_all()  # como en una petición real: nada precargado

    with contar_sentencias(db) as sentencias:
        resultado = _decidir(db, presupuesto_id)

    tipos = Counter(_tipo(s) for s in sentencias)
    assert resultado.efecto_en_orden == "en_reparacion"
    assert resultado.repuestos_reservados == {repuesto_id: 2}
    assert tipos["consumido_por_orden"] == 1, tipos
    assert tipos["select presupuesto"] == 1, tipos
    assert tipos["select version_presupuesto"] == 1, tipos
    assert tipos["select item_presupuesto"] == 1, tipos
    assert tipos["select decision_presupuesto"] == 1, tipos
    assert tipos["releer bloqueada_en"] == 1, tipos


def test_rechazar_lee_la_version_una_sola_vez_y_no_evalua_stock(db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=10)
    presupuesto_id = fabricas.nuevo_presupuesto(
        db, estado="enviado", items=[_item(repuesto)]).presupuesto_id
    db.expire_all()

    with contar_sentencias(db) as sentencias:
        resultado = _decidir(db, presupuesto_id, "rechazado")

    tipos = Counter(_tipo(s) for s in sentencias)
    assert resultado.efecto_en_orden == "cancelado"
    assert tipos["select presupuesto"] == 1, tipos
    assert tipos["select version_presupuesto"] == 1, tipos
    assert tipos["consumido_por_orden"] == 0, tipos
    assert tipos["select movimiento_inventario"] == 0, tipos


def test_aprobar_sigue_completando_bloqueada_en_desde_el_trigger(db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=10)
    presupuesto = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(repuesto)])
    db.expire_all()

    resultado = _decidir(db, presupuesto.presupuesto_id)

    version = resultado.presupuesto.versiones[0]
    assert version.estado == "aprobada"
    assert version.decision is not None and version.decision.decision == "aprobado"
    assert resultado.presupuesto.version_vigente == 1


def test_enviar_lee_la_version_una_sola_vez_y_guarda_la_hora_del_servidor(db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=10)
    presupuesto_id = fabricas.nuevo_presupuesto(
        db, estado="borrador", items=[_item(repuesto)]).presupuesto_id
    db.expire_all()

    with contar_sentencias(db) as sentencias:
        resultado = casos.enviar_version(UnidadDeTrabajo(db), presupuesto_id=presupuesto_id, numero=1)

    tipos = Counter(_tipo(s) for s in sentencias)
    assert resultado.presupuesto.versiones[0].estado == "enviada"
    assert resultado.presupuesto.versiones[0].enviado_en is not None
    assert tipos["select version_presupuesto"] == 1, tipos
    assert tipos["releer enviado_en"] == 1, tipos
    assert tipos["select item_presupuesto"] == 1, tipos
