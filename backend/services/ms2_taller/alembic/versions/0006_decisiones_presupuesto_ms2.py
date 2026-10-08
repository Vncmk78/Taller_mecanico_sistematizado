"""Referencia lógica única para aplicar decisiones de MS3 una sola vez.

Revision ID: 0006_ms2
Revises: 0005_ms2
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_ms2"
down_revision = "0005_ms2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("historial_estado", sa.Column("decision_presupuesto_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_historial_estado_decision_presupuesto_id", "historial_estado", ["decision_presupuesto_id"])
    op.create_check_constraint("decision_presupuesto_positiva", "historial_estado",
                               "decision_presupuesto_id is null or decision_presupuesto_id > 0")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_historial_estado_decision_presupuesto_positiva"), "historial_estado", type_="check")
    op.drop_constraint(op.f("uq_historial_estado_decision_presupuesto_id"), "historial_estado", type_="unique")
    op.drop_column("historial_estado", "decision_presupuesto_id")
