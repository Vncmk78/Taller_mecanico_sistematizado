"""Referencia lógica para aplicar una sola vez el envío inicial de MS3.

Revision ID: 0007_ms2
Revises: 0006_ms2
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_ms2"
down_revision = "0006_ms2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "historial_estado",
        sa.Column("envio_presupuesto_id", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_historial_estado_envio_presupuesto_id",
        "historial_estado",
        ["envio_presupuesto_id"],
    )
    op.create_check_constraint(
        "envio_presupuesto_positivo",
        "historial_estado",
        "envio_presupuesto_id is null or envio_presupuesto_id > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_historial_estado_envio_presupuesto_positivo"),
        "historial_estado",
        type_="check",
    )
    op.drop_constraint(
        op.f("uq_historial_estado_envio_presupuesto_id"),
        "historial_estado",
        type_="unique",
    )
    op.drop_column("historial_estado", "envio_presupuesto_id")
