"""Inicial MS3: proveedor, repuesto, presupuesto, parametro_inventario

Revision ID: 0001_ms3
Revises:
Create Date: 2026-09-16

Crea las tablas iniciales del microservicio de Presupuestos, Repuestos y
Proveedores según el MER (recuadro "BD MS3"): Proveedor, Repuesto (FK local a
Proveedor), Presupuesto (orden_id es REF lógica a MS2, sin FK física) y
ParametroInventario.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_ms3"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proveedor",
        sa.Column("proveedor_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("contacto", sa.String(length=150), nullable=True),
        sa.PrimaryKeyConstraint("proveedor_id", name="pk_proveedor"),
    )

    op.create_table(
        "repuesto",
        sa.Column("repuesto_id", sa.Integer(), nullable=False),
        sa.Column("proveedor_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("umbral_particular", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("repuesto_id", name="pk_repuesto"),
        sa.ForeignKeyConstraint(
            ["proveedor_id"], ["proveedor.proveedor_id"],
            name="fk_repuesto_proveedor_id_proveedor",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_repuesto_proveedor_id", "repuesto", ["proveedor_id"])

    op.create_table(
        "presupuesto",
        sa.Column("presupuesto_id", sa.Integer(), nullable=False),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("presupuesto_id", name="pk_presupuesto"),
        sa.UniqueConstraint("orden_id", name="uq_presupuesto_orden_id"),
    )

    op.create_table(
        "parametro_inventario",
        sa.Column("parametro_id", sa.Integer(), nullable=False),
        sa.Column("umbral_general", sa.Integer(), nullable=False),
        sa.Column("actualizado_por_id", sa.Integer(), nullable=True),
        sa.Column(
            "vigente_desde",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("parametro_id", name="pk_parametro_inventario"),
    )


def downgrade() -> None:
    op.drop_table("parametro_inventario")
    op.drop_index("ix_repuesto_proveedor_id", table_name="repuesto")
    op.drop_table("repuesto")
    op.drop_table("presupuesto")
    op.drop_table("proveedor")
