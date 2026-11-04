"""Índice para el historial general de movimientos — MS3.

Revision ID: 0010_ms3
Revises: 0009_ms3

Semana 9 · "Identificar consultas innecesarias o lentas y proponer ajustes de
índices" (backend/docs/consultas-lentas-y-ajustes-indices.md).

GET /inventario/movimientos sin filtros (el historial de la vista de
inventario) ordena por fecha_hora DESC, movimiento_id DESC y pagina. Ningún
índice empezaba por fecha_hora: con 500.000 movimientos PostgreSQL leía la
tabla entera y la ordenaba (~120 ms por página). Con este índice lee solo las
filas de la página (<1 ms). También lo usa el filtro por tipo.

Solo agrega un índice: no toca datos.
"""
from alembic import op

revision = "0010_ms3"
down_revision = "0009_ms3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_movimiento_inventario_fecha ON movimiento_inventario "
        "(fecha_hora DESC, movimiento_id DESC)"
    )


def downgrade() -> None:
    op.drop_index("ix_movimiento_inventario_fecha", table_name="movimiento_inventario")
