"""Índices de las consultas de inventario y trazabilidad — MS3.

Revision ID: 0008_ms3
Revises: 0007_ms3

Semana 7 · "Revisar índices y consultas utilizadas por inventario y
trazabilidad". Detalle de la revisión: backend/docs/revision-indices-inventario.md.

Reemplaza los índices de una columna de movimiento_inventario por índices
compuestos que además entregan el ORDEN que piden las consultas (sin ordenar
en memoria) y, donde conviene, las columnas leídas (INCLUDE → solo índice):

    ix_movimiento_inventario_saldo           saldo reservado por orden
    ix_movimiento_inventario_repuesto_fecha  movimientos de un repuesto (reemplaza *_repuesto_id)
    ix_movimiento_inventario_orden_fecha     movimientos de una orden   (reemplaza *_orden_id)
    ix_movimiento_inventario_proveedor_fecha ingresos de un proveedor   (reemplaza *_proveedor_id)
    ix_movimiento_inventario_ingresos        ingresos de un repuesto por proveedor

Las FK repuesto_id y proveedor_id siguen cubiertas: son la primera columna de
los índices nuevos. Solo cambia índices: no toca datos.
"""
from alembic import op

revision = "0008_ms3"
down_revision = "0007_ms3"
branch_labels = None
depends_on = None

TABLA = "movimiento_inventario"


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_movimiento_inventario_saldo ON movimiento_inventario "
        "(repuesto_id, movimiento_id) INCLUDE (orden_id, tipo, cantidad) "
        "WHERE orden_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_movimiento_inventario_repuesto_fecha ON movimiento_inventario "
        "(repuesto_id, fecha_hora DESC, movimiento_id DESC)"
    )
    op.execute(
        "CREATE INDEX ix_movimiento_inventario_orden_fecha ON movimiento_inventario "
        "(orden_id, fecha_hora DESC, movimiento_id DESC) WHERE orden_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_movimiento_inventario_proveedor_fecha ON movimiento_inventario "
        "(proveedor_id, fecha_hora DESC, movimiento_id DESC) INCLUDE (repuesto_id, cantidad) "
        "WHERE proveedor_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_movimiento_inventario_ingresos ON movimiento_inventario "
        "(repuesto_id, proveedor_id) INCLUDE (cantidad, fecha_hora) WHERE tipo = 'ingreso'"
    )
    # Quedan cubiertos por los compuestos (misma primera columna).
    op.drop_index("ix_movimiento_inventario_repuesto_id", table_name=TABLA)
    op.drop_index("ix_movimiento_inventario_orden_id", table_name=TABLA)
    op.drop_index("ix_movimiento_inventario_proveedor_id", table_name=TABLA)


def downgrade() -> None:
    op.create_index("ix_movimiento_inventario_proveedor_id", TABLA, ["proveedor_id"])
    op.create_index("ix_movimiento_inventario_orden_id", TABLA, ["orden_id"])
    op.create_index("ix_movimiento_inventario_repuesto_id", TABLA, ["repuesto_id"])
    for nombre in ("ix_movimiento_inventario_ingresos", "ix_movimiento_inventario_proveedor_fecha",
                   "ix_movimiento_inventario_orden_fecha", "ix_movimiento_inventario_repuesto_fecha",
                   "ix_movimiento_inventario_saldo"):
        op.drop_index(nombre, table_name=TABLA)
