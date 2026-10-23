"""Outbox transaccional para eventos de cambios de estado.

Revision ID: 0010_outbox_eventos_ms2
Revises: 0009_ms2
Create Date: 2026-10-23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_outbox_eventos_ms2"
down_revision: Union[str, None] = "0009_ms2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evento_outbox",
        sa.Column("outbox_id", sa.Integer(), nullable=False),
        sa.Column("evento_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "proxima_tentativa_en", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("ultimo_error", sa.String(length=300), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("intentos >= 0", name=op.f("ck_evento_outbox_intentos_no_negativos")),
        sa.PrimaryKeyConstraint("outbox_id", name=op.f("pk_evento_outbox")),
        sa.UniqueConstraint("evento_id", name=op.f("uq_evento_outbox_evento_id")),
    )
    op.create_index(
        "ix_evento_outbox_pendiente",
        "evento_outbox",
        ["proxima_tentativa_en", "outbox_id"],
        postgresql_where=sa.text("publicado_en is null"),
    )


def downgrade() -> None:
    op.drop_index("ix_evento_outbox_pendiente", table_name="evento_outbox")
    op.drop_table("evento_outbox")
