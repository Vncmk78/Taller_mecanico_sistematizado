"""Verifica que las fixtures y fábricas de MS3 entregan datos válidos y coherentes.

Si alguien cambia un modelo, una migración o datos_prueba.py y rompe los datos
de prueba, estas pruebas fallan primero y dicen exactamente qué dejó de cumplirse.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.models import (
    MovimientoInventario,
    ParametroInventario,
    Presupuesto,
    Repuesto,
)
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.tests import fabricas


# ------------------------------------------------------------------- catálogo --

def test_catalogo_carga_todos_los_repuestos_de_datos_prueba(catalogo: dict[str, Repuesto]) -> None:
    esperados = {r.nombre for p in datos.CATALOGO for r in p.repuestos}
    assert set(catalogo) == esperados
    assert len({r.proveedor_id for r in catalogo.values()}) == len(datos.CATALOGO)
    stock = {nombre: r.stock for nombre, r in catalogo.items()}
    assert stock == {r.nombre: r.stock for p in datos.CATALOGO for r in p.repuestos}


def test_catalogo_registra_un_ingreso_inicial_por_repuesto(
    db: Session, catalogo: dict[str, Repuesto]
) -> None:
    for repuesto in catalogo.values():
        ingresos = db.scalars(
            select(MovimientoInventario).where(
                MovimientoInventario.repuesto_id == repuesto.repuesto_id,
                MovimientoInventario.tipo == "ingreso",
            )
        ).all()
        assert [m.cantidad for m in ingresos] == [repuesto.stock]


def test_repuesto_bajo_umbral_esta_bajo_su_umbral(
    repuesto_bajo_umbral: Repuesto, uow: UnidadDeTrabajo
) -> None:
    assert repuesto_bajo_umbral.stock < repuesto_bajo_umbral.umbral_particular
    bajo = uow.repuestos.bajo_umbral(umbral_general=datos.UMBRAL_GENERAL)
    assert repuesto_bajo_umbral in bajo


def test_catalogo_se_puede_cargar_dos_veces_sin_chocar(db: Session) -> None:
    primero = fabricas.cargar_catalogo(db)
    segundo = fabricas.cargar_catalogo(db)
    assert {r.repuesto_id for r in primero.values()}.isdisjoint(
        {r.repuesto_id for r in segundo.values()}
    )


# ----------------------------------------------------------------- inventario --

def test_umbral_general_queda_unico_y_vigente(db: Session, umbral_general: ParametroInventario) -> None:
    vigentes = db.scalar(
        select(func.count()).select_from(ParametroInventario)
        .where(ParametroInventario.vigente_hasta.is_(None))
    )
    assert vigentes == 1
    assert umbral_general.umbral_general == datos.UMBRAL_GENERAL
    # Pedirlo de nuevo reemplaza el vigente, no crea un segundo.
    otro = fabricas.umbral_general_vigente(db, valor=8)
    assert db.get(ParametroInventario, umbral_general.parametro_id).vigente_hasta is not None
    assert otro.vigente_hasta is None


def test_movimiento_de_consumo_recibe_orden_automaticamente(db: Session) -> None:
    movimiento = fabricas.nuevo_movimiento(db, fabricas.nuevo_repuesto(db), tipo="consumo")
    assert movimiento.orden_id is not None
    assert movimiento.clave_operacion


# ---------------------------------------------------------------- presupuesto --

def test_presupuesto_borrador_es_editable(presupuesto_borrador: Presupuesto) -> None:
    version = presupuesto_borrador.versiones[0]
    assert version.numero == 1 and version.editable and not version.bloqueada
    assert version.decision is None


def test_presupuesto_enviado_esta_congelado_sin_decision(presupuesto_enviado: Presupuesto) -> None:
    version = presupuesto_enviado.versiones[0]
    assert version.enviada and not version.editable and version.decision is None


def test_presupuesto_aprobado_queda_bloqueado_y_vigente(presupuesto_aprobado: Presupuesto) -> None:
    version = presupuesto_aprobado.versiones[0]
    assert version.bloqueada
    assert version.decision.decision == "aprobado"
    assert presupuesto_aprobado.version_vigente is version


def test_presupuesto_rechazado_tiene_motivo_y_no_vigente(presupuesto_rechazado: Presupuesto) -> None:
    version = presupuesto_rechazado.versiones[0]
    assert version.decision.decision == "rechazado" and version.decision.motivo
    assert not version.bloqueada
    assert presupuesto_rechazado.version_vigente is None


def test_presupuesto_ejemplo_coincide_con_la_semilla(presupuesto_ejemplo: Presupuesto) -> None:
    version = presupuesto_ejemplo.versiones[0]
    assert sum(i.subtotal for i in version.items) == datos.TOTAL_PRESUPUESTO_EJEMPLO
    tipos = sorted(i.tipo for i in version.items)
    assert tipos == ["mano_de_obra", "repuesto"]


def test_cada_presupuesto_usa_una_orden_distinta(db: Session) -> None:
    ordenes = {fabricas.nuevo_presupuesto(db).orden_id for _ in range(3)}
    assert len(ordenes) == 3


def test_estado_desconocido_es_un_error_de_la_fabrica(db: Session) -> None:
    with pytest.raises(ValueError):
        fabricas.nuevo_presupuesto(db, estado="pagado")
