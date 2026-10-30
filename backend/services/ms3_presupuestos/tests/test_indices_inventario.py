"""Índices de las consultas de inventario y trazabilidad (migración 0008_ms3).

Con `enable_seqscan = off`, el EXPLAIN de la consulta REAL que arma el
repositorio debe usar su índice. Si alguien cambia una consulta (o borra un
índice) y deja de coincidir, la prueba falla y obliga a revisar el índice.
Detalle y mediciones: backend/docs/revision-indices-inventario.md.
"""
from __future__ import annotations

import pytest
from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from services.ms3_presupuestos.models import MovimientoInventario
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.repositorios import RepositorioMovimientos

M = MovimientoInventario


def _plan(db: Session, consulta: Select) -> str:
    """EXPLAIN de la consulta tal cual la ejecuta SQLAlchemy (mismos parámetros)."""
    with db.begin_nested():
        db.execute(text("SET LOCAL enable_seqscan = off"))
        db.execute(text("SET LOCAL enable_bitmapscan = off"))
        conexion = db.connection()
        compilada = consulta.compile(dialect=conexion.dialect,
                                     compile_kwargs={"render_postcompile": True})
        filas = conexion.exec_driver_sql(f"EXPLAIN {compilada}", compilada.params).scalars().all()
    return "\n".join(filas)


def _consulta_saldo(ids: list[int]) -> Select:
    """La misma consulta de RepositorioMovimientos.comprometido_por_ordenes."""
    return (select(M.repuesto_id, M.orden_id, M.tipo, M.cantidad)
            .where(M.repuesto_id.in_(ids), M.orden_id.is_not(None))
            .order_by(M.repuesto_id, M.movimiento_id))


def _listado(**filtros) -> Select:
    """La consulta del listado paginado de movimientos (RepositorioMovimientos.buscar)."""
    repo = RepositorioMovimientos.__new__(RepositorioMovimientos)
    base = {"repuesto_id": None, "orden_id": None, "tipo": None} | filtros
    return (repo._filtro(**base)
            .order_by(M.fecha_hora.desc(), M.movimiento_id.desc()).limit(50))


@pytest.mark.parametrize(("descripcion", "consulta", "indice"), [
    ("saldo reservado de un repuesto", lambda: _consulta_saldo([1]), "ix_movimiento_inventario_saldo"),
    ("saldo reservado de varios repuestos", lambda: _consulta_saldo([1, 2, 3]),
     "ix_movimiento_inventario_saldo"),
    ("movimientos de un repuesto", lambda: _listado(repuesto_id=1),
     "ix_movimiento_inventario_repuesto_fecha"),
    ("movimientos de una orden", lambda: _listado(orden_id=1), "ix_movimiento_inventario_orden_fecha"),
    ("ingresos de un proveedor", lambda: _listado(proveedor_id=1),
     "ix_movimiento_inventario_proveedor_fecha"),
    ("consumido por orden",
     lambda: select(M.repuesto_id, func.sum(M.cantidad))
     .where(M.orden_id == 1, M.tipo == "consumo").group_by(M.repuesto_id),
     "ix_movimiento_inventario_orden_fecha"),
    ("unidades entregadas por un proveedor",
     lambda: select(M.repuesto_id, func.sum(M.cantidad)).where(M.proveedor_id == 1)
     .group_by(M.repuesto_id),
     "ix_movimiento_inventario_proveedor_fecha"),
    ("ingresos de un repuesto por proveedor",
     lambda: select(M.proveedor_id, func.count(), func.sum(M.cantidad), func.min(M.fecha_hora))
     .where(M.repuesto_id == 1, M.tipo == "ingreso").group_by(M.proveedor_id),
     "ix_movimiento_inventario_ingresos"),
])
def test_la_consulta_usa_su_indice(db: Session, descripcion: str, consulta, indice: str) -> None:
    plan = _plan(db, consulta())
    assert indice in plan, f"{descripcion}: no usa {indice}\n{plan}"


@pytest.mark.parametrize("consulta", [
    lambda: _listado(repuesto_id=1),
    lambda: _listado(orden_id=1),
    lambda: _listado(proveedor_id=1),
    lambda: _consulta_saldo([1]),
])
def test_el_indice_entrega_el_orden_sin_ordenar_en_memoria(db: Session, consulta) -> None:
    assert "Sort" not in _plan(db, consulta())


def test_el_saldo_se_lee_solo_del_indice(db: Session) -> None:
    assert "Index Only Scan using ix_movimiento_inventario_saldo" in _plan(db, _consulta_saldo([1]))


def test_existen_los_indices_y_no_quedan_los_reemplazados(db: Session) -> None:
    nombres = set(db.execute(text(
        "select indexname from pg_indexes where tablename = 'movimiento_inventario'")).scalars())
    assert {"ix_movimiento_inventario_saldo", "ix_movimiento_inventario_repuesto_fecha",
            "ix_movimiento_inventario_orden_fecha", "ix_movimiento_inventario_proveedor_fecha",
            "ix_movimiento_inventario_ingresos"} <= nombres
    assert not nombres & {"ix_movimiento_inventario_repuesto_id", "ix_movimiento_inventario_orden_id",
                          "ix_movimiento_inventario_proveedor_id"}


def test_saldo_de_varios_repuestos_en_una_sola_consulta(db: Session) -> None:
    """Validar o reservar N repuestos no hace N consultas de saldo."""
    from services.ms3_presupuestos.tests import fabricas

    repuestos = [fabricas.nuevo_repuesto(db, stock=10) for _ in range(5)]
    orden = fabricas.nuevo_orden_id()
    for r in repuestos:
        fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=2, orden_id=orden)

    consultas: list[str] = []
    conexion = db.connection()

    from sqlalchemy import event

    def contar(_c, _cursor, sentencia, *_args) -> None:
        if "movimiento_inventario" in sentencia:
            consultas.append(sentencia)

    event.listen(conexion, "before_cursor_execute", contar)
    try:
        saldos = UnidadDeTrabajo(db).movimientos.comprometido_por_ordenes(
            [r.repuesto_id for r in repuestos])
    finally:
        event.remove(conexion, "before_cursor_execute", contar)

    assert len(consultas) == 1
    assert saldos == {r.repuesto_id: {orden: 2} for r in repuestos}
