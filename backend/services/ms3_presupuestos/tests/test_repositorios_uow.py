"""Pruebas del patrón repositorio + unidad de trabajo de MS3 contra PostgreSQL.

Usan la fixture `db` (conftest.py): una sesión dentro de una transacción
externa que se revierte al final. Con `join_transaction_mode="create_savepoint"`
el commit/rollback de la unidad de trabajo actúa sobre SAVEPOINTs, así que
se puede comprobar su comportamiento real sin dejar datos.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from services.ms3_presupuestos.datos_prueba import ADMIN_ID as ADMIN
from services.ms3_presupuestos.datos_prueba import MECANICO_ID as MECANICO
from services.ms3_presupuestos.models import (
    ItemPresupuesto,
    MovimientoInventario,
    ParametroInventario,
    Presupuesto,
    Proveedor,
    VersionPresupuesto,
)
from services.ms3_presupuestos.persistencia import (
    ConflictoDeDatos,
    RecursoNoEncontrado,
    ReglaDeDatosViolada,
    UnidadDeTrabajo,
)
from services.ms3_presupuestos.tests.fabricas import nuevo_proveedor


# La fixture `uow` vive en conftest.py.


# ----------------------------------------------------------------- repositorios --

def test_agregar_asigna_id_y_obtener_lo_encuentra(uow: UnidadDeTrabajo) -> None:
    with uow.transaccion():
        proveedor = nuevo_proveedor(uow.sesion, "Prov UoW")
    assert proveedor.proveedor_id is not None
    assert uow.proveedores.obtener(proveedor.proveedor_id) is proveedor
    assert uow.proveedores.buscar_por_nombre("Prov UoW") is proveedor


def test_obtener_o_error_lanza_404_si_no_existe(uow: UnidadDeTrabajo) -> None:
    with pytest.raises(RecursoNoEncontrado):
        uow.repuestos.obtener_o_error(987654321)


def test_listar_pagina_en_orden_estable(uow: UnidadDeTrabajo) -> None:
    with uow.transaccion():
        for i in range(5):
            uow.proveedores.agregar(Proveedor(nombre=f"Pag {i}", contacto="c"))
    total = uow.proveedores.contar()
    primera = uow.proveedores.listar(desde=0, limite=2)
    segunda = uow.proveedores.listar(desde=2, limite=2)
    assert total >= 5 and len(primera) == 2 and len(segunda) == 2
    ids = [p.proveedor_id for p in [*primera, *segunda]]
    assert ids == sorted(ids) and len(set(ids)) == 4


def test_repuestos_de_proveedor_y_bajo_umbral(uow: UnidadDeTrabajo) -> None:
    with uow.transaccion():
        proveedor = nuevo_proveedor(uow.sesion, "Prov UoW")
    nombres = [r.nombre for r in uow.repuestos.de_proveedor(proveedor.proveedor_id)]
    assert nombres == ["Prov UoW disco", "Prov UoW filtro"]
    bajo = {r.nombre for r in uow.repuestos.bajo_umbral(umbral_general=5)}
    assert "Prov UoW disco" in bajo          # 1 < 3 (umbral particular)
    assert "Prov UoW filtro" not in bajo     # 50 >= 5 (umbral general)


def test_obtener_para_actualizar_bloquea_y_devuelve_la_fila(uow: UnidadDeTrabajo) -> None:
    with uow.transaccion():
        repuesto = nuevo_proveedor(uow.sesion, "Prov UoW").repuestos[0]
    with uow.transaccion():
        bloqueado = uow.repuestos.obtener_para_actualizar(repuesto.repuesto_id)
        bloqueado.stock += 5
    assert uow.repuestos.obtener(repuesto.repuesto_id).stock == 6


def test_movimientos_por_clave_y_por_orden(uow: UnidadDeTrabajo) -> None:
    with uow.transaccion():
        repuesto = nuevo_proveedor(uow.sesion, "Prov UoW").repuestos[1]
        uow.movimientos.agregar(MovimientoInventario(
            clave_operacion="uow-mov-1", repuesto=repuesto, orden_id=777,
            tipo="compromiso", cantidad=2, registrado_por_id=MECANICO))
    assert uow.movimientos.por_clave_operacion("uow-mov-1").cantidad == 2
    assert [m.clave_operacion for m in uow.movimientos.de_orden(777)] == ["uow-mov-1"]


def test_parametro_vigente_y_presupuesto_de_orden(uow: UnidadDeTrabajo, db: Session) -> None:
    with uow.transaccion():
        vigente = uow.parametros.vigente()
        if vigente is None:
            vigente = uow.parametros.agregar(ParametroInventario(umbral_general=5, actualizado_por_id=ADMIN))
        presupuesto = Presupuesto(orden_id=880001)
        presupuesto.versiones.append(VersionPresupuesto(numero=1, creado_por_id=MECANICO))
        uow.presupuestos.agregar(presupuesto)
    assert uow.parametros.vigente() is vigente
    assert uow.presupuestos.de_orden(880001) is presupuesto
    assert uow.presupuestos.de_orden(880002) is None


# ------------------------------------------------------------ unidad de trabajo --

def test_error_en_el_caso_de_uso_revierte_todo(uow: UnidadDeTrabajo) -> None:
    with pytest.raises(ValueError):
        with uow.transaccion():
            nuevo_proveedor(uow.sesion, "Prov Revertido")
            raise ValueError("falla a mitad del caso de uso")
    assert uow.proveedores.buscar_por_nombre("Prov Revertido") is None


def test_clave_duplicada_se_traduce_a_conflicto(uow: UnidadDeTrabajo) -> None:
    with uow.transaccion():
        uow.proveedores.agregar(Proveedor(nombre="Prov Dup", contacto="c"))
    with pytest.raises(ConflictoDeDatos) as info:
        with uow.transaccion():
            uow.proveedores.agregar(Proveedor(nombre="Prov Dup", contacto="c"))
    assert info.value.restriccion == "uq_proveedor_nombre"
    assert info.value.codigo_http == 409


def test_check_de_la_base_se_traduce_a_regla_violada(uow: UnidadDeTrabajo) -> None:
    with pytest.raises(ReglaDeDatosViolada) as info:
        with uow.transaccion():
            nuevo_proveedor(uow.sesion, "Prov UoW").repuestos[0].stock = -1
            uow.sesion.flush()
    assert info.value.restriccion == "ck_repuesto_stock_no_negativo"


def test_trigger_de_versionado_llega_con_su_mensaje(uow: UnidadDeTrabajo) -> None:
    with uow.transaccion():
        presupuesto = Presupuesto(orden_id=880010)
        version = VersionPresupuesto(numero=1, creado_por_id=MECANICO)
        version.items.append(ItemPresupuesto(tipo="mano_de_obra", descripcion="Rev",
                                             cantidad=Decimal("1"), precio_unitario=Decimal("1000")))
        presupuesto.versiones.append(version)
        uow.presupuestos.agregar(presupuesto)
        uow.sesion.refresh(version)
        version.enviado_en = version.creado_en
    with pytest.raises(ReglaDeDatosViolada, match="ya fue enviada"):
        with uow.transaccion():
            version.items[0].precio_unitario = Decimal("1")
            uow.sesion.flush()


def test_transaccion_anidada_revierte_solo_su_parte(uow: UnidadDeTrabajo) -> None:
    with uow.transaccion():
        uow.proveedores.agregar(Proveedor(nombre="Prov Externo", contacto="c"))
        with pytest.raises(ConflictoDeDatos):
            with uow.transaccion():               # SAVEPOINT
                uow.proveedores.agregar(Proveedor(nombre="Prov Externo", contacto="c"))
        uow.proveedores.agregar(Proveedor(nombre="Prov Externo 2", contacto="c"))
    assert uow.proveedores.buscar_por_nombre("Prov Externo") is not None
    assert uow.proveedores.buscar_por_nombre("Prov Externo 2") is not None
