"""Inicial MS2: cliente, vehiculo

Revision ID: 0001_ms2
Revises:
Create Date: 2026-09-10

Crea las tablas iniciales del microservicio de Vehículos y Órdenes de Trabajo
según el MER (recuadro "BD MS2"): Cliente y Vehiculo. `cliente.usuario_id` es una
referencia lógica a MS1 (sin FK física, §8); `vehiculo.cliente_id` sí es FK local.
La patente es única.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0001_ms2"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- CLIENTE ---
    op.create_table(
        "cliente",
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        # usuario_id: REF lógica a Usuario (MS1). Sin ForeignKey física (§8).
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.PrimaryKeyConstraint("cliente_id", name="pk_cliente"),
        sa.UniqueConstraint("usuario_id", name="uq_cliente_usuario_id"),
    )

    # --- VEHICULO ---
    op.create_table(
        "vehiculo",
        sa.Column("vehiculo_id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("patente", sa.String(length=10), nullable=False),
        sa.Column("marca", sa.String(length=60), nullable=False),
        sa.Column("modelo", sa.String(length=60), nullable=False),
        sa.Column("anio", sa.Integer(), nullable=True),
        sa.Column("kilometraje", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("vehiculo_id", name="pk_vehiculo"),
        sa.ForeignKeyConstraint(
            ["cliente_id"], ["cliente.cliente_id"],
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
