"""Migración inicial: usuario, cliente, vehiculo

Revision ID: 0001
Revises:
Create Date: 2026-09-07
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tipo enumerado para el rol del usuario (cliente | mecanico | admin).
rol_usuario = sa.Enum("cliente", "mecanico", "admin", name="rol_usuario")


def upgrade() -> None:
    # --- USUARIO ---
    op.create_table(
        "usuario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("rol", rol_usuario, nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_usuario"),
        sa.UniqueConstraint("email", name="uq_usuario_email"),
    )
    op.create_index("ix_usuario_email", "usuario", ["email"], unique=True)

    # --- CLIENTE ---
    op.create_table(
        "cliente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_cliente"),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"],
            name="fk_cliente_usuario_id_usuario",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("usuario_id", name="uq_cliente_usuario_id"),
    )

    # --- VEHICULO ---
    op.create_table(
        "vehiculo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("patente", sa.String(length=10), nullable=False),
        sa.Column("marca", sa.String(length=60), nullable=False),
        sa.Column("modelo", sa.String(length=60), nullable=False),
        sa.Column("anio", sa.Integer(), nullable=True),
        sa.Column("kilometraje", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_vehiculo"),
        sa.ForeignKeyConstraint(
            ["cliente_id"], ["cliente.id"],
            name="fk_vehiculo_cliente_id_cliente",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("patente", name="uq_vehiculo_patente"),
    )
    op.create_index("ix_vehiculo_cliente_id", "vehiculo", ["cliente_id"])


def downgrade() -> None:
    op.drop_index("ix_vehiculo_cliente_id", table_name="vehiculo")
    op.drop_table("vehiculo")
    op.drop_table("cliente")
    op.drop_index("ix_usuario_email", table_name="usuario")
    op.drop_table("usuario")
    # Elimina el tipo enumerado en PostgreSQL.
    rol_usuario.drop(op.get_bind(), checkfirst=True)
