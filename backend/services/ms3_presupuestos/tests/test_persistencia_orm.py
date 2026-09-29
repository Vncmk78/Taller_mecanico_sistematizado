"""Pruebas básicas de persistencia ORM de MS3 (Semana 4).

Usan los modelos ORM (no SQL directo) contra PostgreSQL migrado y comprueban:

1. Que se guarda y se lee con sus relaciones: proveedor → repuestos,
   presupuesto → versiones → ítems.
2. Que la base rechaza datos inválidos (CHECK / UNIQUE): stock negativo,
   clave de operación repetida, consumo sin orden, dos umbrales vigentes,
   ítem de repuesto sin repuesto, rechazo sin motivo.
3. Que los triggers de versionado funcionan a través del ORM: numeración
   correlativa, versión enviada congelada, aprobar bloquea, decisión inmutable
   y la última aprobación sigue vigente si se rechaza una modificación.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.ms3_presupuestos.models import (
    DecisionPresupuesto,
    HistorialUmbral,
    ItemPresupuesto,
    MovimientoInventario,
    ParametroInventario,
    Presupuesto,
    Proveedor,
    Repuesto,
    VersionPresupuesto,
)

ADMIN, MECANICO, CLIENTE = 3, 2, 1


# ------------------------------------------------------------------ helpers --

def _rechaza(db: Session, *objetos) -> None:
    """Afirma que guardar los objetos viola una regla de la base.

    Usa un SAVEPOINT para que la sesión siga usable después del error.
    """
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add_all(objetos)
            db.flush()


def _repuesto(db: Session, nombre: str = "Pastillas de prueba", stock: int = 10) -> Repuesto:
    proveedor = Proveedor(nombre=f"Proveedor {nombre}", contacto="prueba@taller.cl")
    repuesto = Repuesto(proveedor=proveedor, nombre=nombre, stock=stock)
    db.add(proveedor)
    db.flush()
    return repuesto


def _presupuesto(db: Session, orden_id: int = 900001) -> VersionPresupuesto:
    """Presupuesto con versión 1 en borrador y un ítem de mano de obra."""
    presupuesto = Presupuesto(orden_id=orden_id)
    version = VersionPresupuesto(numero=1, creado_por_id=MECANICO)
    version.items.append(ItemPresupuesto(
        tipo="mano_de_obra", descripcion="Revision", cantidad=Decimal("1"),
        precio_unitario=Decimal("20000"),
    ))
    presupuesto.versiones.append(version)
    db.add(presupuesto)
    db.flush()
    return version


def _enviar(db: Session, version: VersionPresupuesto) -> None:
    # Dentro de la transacción de prueba now() es constante: se envía en el
    # mismo instante de creación para que la decisión (now()) no quede antes.
    db.refresh(version)
    version.enviado_en = version.creado_en
    db.flush()


# ------------------------------------------------ 1) guardar y leer relaciones --

def test_proveedor_con_repuestos_se_guarda_y_se_lee(db: Session) -> None:
    proveedor = Proveedor(nombre="Frenos Prueba", contacto="frenos@prueba.cl")
    proveedor.repuestos += [Repuesto(nombre="Disco", stock=2, umbral_particular=3),
                            Repuesto(nombre="Pastilla", stock=8)]
    db.add(proveedor)
    db.flush()
    db.expire_all()

    leido = db.get(Proveedor, proveedor.proveedor_id)
    assert sorted(r.nombre for r in leido.repuestos) == ["Disco", "Pastilla"]
    assert all(r.proveedor is leido for r in leido.repuestos)
    assert next(r for r in leido.repuestos if r.nombre == "Pastilla").stock == 8


def test_presupuesto_con_version_e_items_calcula_subtotal(db: Session) -> None:
    repuesto = _repuesto(db)
    version = _presupuesto(db)
    version.items.append(ItemPresupuesto(
        tipo="repuesto", repuesto=repuesto, descripcion="Pastillas",
        cantidad=Decimal("2"), precio_unitario=Decimal("15000.50"),
    ))
    db.flush()
    db.expire_all()

    presupuesto = db.get(Presupuesto, version.presupuesto_id)
    assert [v.numero for v in presupuesto.versiones] == [1]
    assert presupuesto.siguiente_numero == 2
    assert sum(i.subtotal for i in presupuesto.versiones[0].items) == Decimal("50001.00")
    assert presupuesto.versiones[0].editable is True


def test_movimiento_de_inventario_queda_asociado_al_repuesto(db: Session) -> None:
    repuesto = _repuesto(db)
    db.add(MovimientoInventario(clave_operacion="op-orm-1", repuesto=repuesto, orden_id=10,
                                tipo="compromiso", cantidad=2, registrado_por_id=MECANICO))
    db.flush()
    db.expire_all()
    assert [m.tipo for m in db.get(Repuesto, repuesto.repuesto_id).movimientos] == ["compromiso"]


# ------------------------------------------------- 2) restricciones (CHECK/UK) --

def test_stock_negativo_es_rechazado(db: Session) -> None:
    proveedor = Proveedor(nombre="P", contacto="c")
    _rechaza(db, proveedor, Repuesto(proveedor=proveedor, nombre="X", stock=-1))


def test_clave_de_operacion_repetida_es_rechazada(db: Session) -> None:
    repuesto = _repuesto(db)
    db.add(MovimientoInventario(clave_operacion="op-dup", repuesto=repuesto, orden_id=10,
                                tipo="consumo", cantidad=1, registrado_por_id=MECANICO))
    db.flush()
    _rechaza(db, MovimientoInventario(clave_operacion="op-dup", repuesto=repuesto, orden_id=10,
                                      tipo="consumo", cantidad=1, registrado_por_id=MECANICO))


def test_consumo_sin_orden_es_rechazado(db: Session) -> None:
    repuesto = _repuesto(db)
    _rechaza(db, MovimientoInventario(clave_operacion="op-sin-orden", repuesto=repuesto,
                                      tipo="consumo", cantidad=1, registrado_por_id=MECANICO))


def test_solo_un_umbral_general_vigente(db: Session) -> None:
    # Cierra cualquier parámetro vigente previo dentro de la transacción de prueba.
    for vigente in db.query(ParametroInventario).filter(ParametroInventario.vigente_hasta.is_(None)):
        vigente.vigente_hasta = datetime.now(timezone.utc) + timedelta(seconds=1)
    db.add(ParametroInventario(umbral_general=5, actualizado_por_id=ADMIN))
    db.flush()
    _rechaza(db, ParametroInventario(umbral_general=7, actualizado_por_id=ADMIN))


def test_umbral_general_sin_valor_nuevo_es_rechazado(db: Session) -> None:
    _rechaza(db, HistorialUmbral(repuesto_id=None, valor_anterior=5, valor_nuevo=None,
                                 administrador_id=ADMIN))


def test_item_de_repuesto_sin_repuesto_es_rechazado(db: Session) -> None:
    version = _presupuesto(db)
    _rechaza(db, ItemPresupuesto(version_id=version.version_id, tipo="repuesto",
                                 descripcion="Sin repuesto", cantidad=1, precio_unitario=1))


def test_un_solo_presupuesto_por_orden(db: Session) -> None:
    _presupuesto(db, orden_id=900002)
    _rechaza(db, Presupuesto(orden_id=900002))


# ------------------------------------------ 3) versionado y bloqueo (triggers) --

def test_numeracion_de_versiones_es_correlativa(db: Session) -> None:
    version = _presupuesto(db)
    _rechaza(db, VersionPresupuesto(presupuesto_id=version.presupuesto_id, numero=3,
                                    creado_por_id=MECANICO))


def test_version_enviada_no_admite_cambios_en_items(db: Session) -> None:
    version = _presupuesto(db)
    _enviar(db, version)
    assert version.editable is False
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            version.items[0].precio_unitario = Decimal("1")
            db.flush()


def test_no_se_decide_sobre_una_version_en_borrador(db: Session) -> None:
    version = _presupuesto(db)
    _rechaza(db, DecisionPresupuesto(version_id=version.version_id,
                                     cliente_usuario_id=CLIENTE, decision="aprobado"))


def test_rechazo_sin_motivo_es_rechazado(db: Session) -> None:
    version = _presupuesto(db)
    _enviar(db, version)
    _rechaza(db, DecisionPresupuesto(version_id=version.version_id,
                                     cliente_usuario_id=CLIENTE, decision="rechazado"))


def test_aprobar_bloquea_la_version_y_la_decision_es_inmutable(db: Session) -> None:
    version = _presupuesto(db)
    _enviar(db, version)
    decision = DecisionPresupuesto(version_id=version.version_id,
                                   cliente_usuario_id=CLIENTE, decision="aprobado")
    db.add(decision)
    db.flush()
    db.refresh(version)

    assert version.bloqueada is True
    assert version.presupuesto.version_vigente is version
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            decision.decision = "rechazado"
            decision.motivo = "cambio de opinion"
            db.flush()


def test_rechazar_modificacion_mantiene_vigente_la_ultima_aprobada(db: Session) -> None:
    v1 = _presupuesto(db)
    _enviar(db, v1)
    db.add(DecisionPresupuesto(version_id=v1.version_id, cliente_usuario_id=CLIENTE,
                               decision="aprobado"))
    db.flush()

    v2 = VersionPresupuesto(presupuesto_id=v1.presupuesto_id, numero=2,
                            creado_por_id=MECANICO, es_modificacion=True)
    db.add(v2)
    db.flush()
    _enviar(db, v2)
    db.add(DecisionPresupuesto(version_id=v2.version_id, cliente_usuario_id=CLIENTE,
                               decision="rechazado", motivo="Muy caro"))
    db.flush()
    db.expire_all()

    presupuesto = db.get(Presupuesto, v1.presupuesto_id)
    assert [v.numero for v in presupuesto.versiones] == [1, 2]
    assert presupuesto.version_vigente.numero == 1
    assert presupuesto.versiones[1].bloqueada is False
