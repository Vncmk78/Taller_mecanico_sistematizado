"""Nombre de repuesto único por proveedor (sin distinguir mayúsculas) — MS3.

Revision ID: 0005_ms3
Revises: 0004_ms3

Semana 5 · "Implementar persistencia y endpoints de repuestos y proveedores".
Evita que un mismo proveedor tenga "Filtro de aceite" y "filtro de aceite"
como repuestos distintos (el stock quedaría repartido entre dos filas).
Índice único de expresión: (proveedor_id, lower(nombre)).

Si una base ya tuviera duplicados, el upgrade falla con el par repetido y
hay que unificarlos antes (no se borra nada automáticamente).
"""
from alembic import op

revision = "0005_ms3"
down_revision = "0004_ms3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_repuesto_proveedor_nombre "
        "ON repuesto (proveedor_id, lower(nombre))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_repuesto_proveedor_nombre")
