"""Una sola orden activa por vehículo; rechaza duplicados sin corregir datos.

Revision ID: 0013_orden_activa_ms2
Revises: 0012_integracion_ms2
"""
from itertools import groupby

from alembic import op
from sqlalchemy import text

revision = "0013_orden_activa_ms2"
down_revision = "0012_integracion_ms2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conexion = op.get_bind()
    if conexion.dialect.name == "postgresql":
        # Impide que una escritura cree duplicados entre el diagnóstico y el
        # índice. El lock dura hasta terminar o revertir la migración.
        conexion.execute(text("LOCK TABLE orden_trabajo IN SHARE ROW EXCLUSIVE MODE"))
    duplicadas = conexion.execute(text(
        "SELECT vehiculo_id, orden_id FROM orden_trabajo "
        "WHERE estado_codigo NOT IN (7, 8) AND vehiculo_id IN ("
        "SELECT vehiculo_id FROM orden_trabajo WHERE estado_codigo NOT IN (7, 8) "
        "GROUP BY vehiculo_id HAVING count(*) > 1) ORDER BY vehiculo_id, orden_id"
    )).all()
    if duplicadas:
        casos = "; ".join(
            f"vehículo {vehiculo}: órdenes {', '.join(str(f.orden_id) for f in filas)}"
            for vehiculo, filas in groupby(duplicadas, key=lambda f: f.vehiculo_id)
        )
        raise RuntimeError(
            "No se puede aplicar una orden activa por vehículo: " + casos
            + ". No se modificaron órdenes; resolver los casos antes de reintentar."
        )
    op.create_index(
        "uq_orden_activa_por_vehiculo", "orden_trabajo", ["vehiculo_id"], unique=True,
        postgresql_where=text("estado_codigo NOT IN (7, 8)"),
        sqlite_where=text("estado_codigo NOT IN (7, 8)"),
    )


def downgrade() -> None:
    op.drop_index("uq_orden_activa_por_vehiculo", table_name="orden_trabajo")
