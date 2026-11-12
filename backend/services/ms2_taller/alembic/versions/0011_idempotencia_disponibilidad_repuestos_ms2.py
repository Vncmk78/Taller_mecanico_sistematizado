"""Conserva la clave de aplicación de disponibilidad de repuestos.

Revision ID: 0011_disponibilidad_repuestos_ms2
Revises: 0010_outbox_eventos_ms2
Create Date: 2026-10-23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_disponibilidad_repuestos_ms2"
down_revision: Union[str, None] = "0010_outbox_eventos_ms2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "historial_estado",
        sa.Column("disponibilidad_repuestos_clave_operacion", sa.String(100), nullable=True),
    )
    op.create_unique_constraint(
        "uq_historial_estado_disponibilidad_clave_operacion",
        "historial_estado",
        ["disponibilidad_repuestos_clave_operacion"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_historial_estado_disponibilidad_clave_operacion",
        "historial_estado",
        type_="unique",
    )
    op.drop_column("historial_estado", "disponibilidad_repuestos_clave_operacion")
