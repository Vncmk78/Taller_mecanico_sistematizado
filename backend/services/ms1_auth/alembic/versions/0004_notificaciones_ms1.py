"""Avisos internos idempotentes para cambios de estado de órdenes.

Revision ID: 0004_notificaciones_ms1
Revises: 0003_auditoria_roles_ms1
Create Date: 2026-10-23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_notificaciones_ms1"
down_revision: Union[str, None] = "0003_auditoria_roles_ms1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notificacion",
        sa.Column("notificacion_id", sa.Integer(), nullable=False),
        sa.Column("evento_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("destinatario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=60), nullable=False),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("vehiculo_id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=120), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("ocurrido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["destinatario_id"], ["usuario.usuario_id"],
            name=op.f("fk_notificacion_destinatario_id_usuario"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notificacion_id", name=op.f("pk_notificacion")),
        sa.UniqueConstraint("evento_id", name=op.f("uq_notificacion_evento_id")),
    )
    op.create_index(
        "ix_notificacion_destinatario_id", "notificacion", ["destinatario_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_notificacion_destinatario_id", table_name="notificacion")
    op.drop_table("notificacion")
