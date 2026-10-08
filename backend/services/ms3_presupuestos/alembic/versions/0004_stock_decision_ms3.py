"""Conserva la disponibilidad evaluada al aprobar para reintentos estables.

Revision ID: 0004_ms3
Revises: 0003_ms3
No rellena decisiones históricas con el stock actual.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_ms3"
down_revision = "0003_ms3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("decision_presupuesto", sa.Column("repuestos_disponibles", sa.Boolean(), nullable=True))
    op.create_check_constraint("stock_solo_aprobacion", "decision_presupuesto",
                               "decision = 'aprobado' or repuestos_disponibles is null")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_decision_presupuesto_stock_solo_aprobacion"), "decision_presupuesto", type_="check")
    op.drop_column("decision_presupuesto", "repuestos_disponibles")
