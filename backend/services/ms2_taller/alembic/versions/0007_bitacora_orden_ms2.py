"""Bitácora del mecánico: observaciones, acciones y repuestos — MS2

Revision ID: 0007_ms2
Revises: 0006_ms2
Create Date: 2026-10-14

Crea las tablas aditivas del flujo del mecánico (RF-11). La bitácora registra
lo que el mecánico observa y ejecuta sobre una orden sin cambiar su estado, por
lo que no puede reutilizar `historial_estado` (su CHECK `cambio_real` exige una
transición):

- bitacora_orden: cada observación o acción; guarda el autor lógico de MS1 (§8),
  el tipo ('observacion' / 'accion'), el texto y la fecha/hora.
- bitacora_repuesto: repuestos (texto libre y cantidad) utilizados en una acción.
  NO referencia el catálogo de repuestos de MS3: las bases están aisladas (§8).

Las FK son locales a MS2 y RESTRICT (la trazabilidad no se borra). No se
modifican ni reescriben las tablas ni los datos existentes.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0007_ms2"
down_revision: Union[str, None] = "0006_ms2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- BITÁCORA DE LA ORDEN (observaciones y acciones) ---
    op.create_table(
        "bitacora_orden",
        sa.Column("bitacora_id", sa.Integer(), nullable=False),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("autor_usuario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=12), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo in ('observacion', 'accion')",
            name=op.f("ck_bitacora_orden_tipo_valido"),
        ),
        sa.CheckConstraint(
            "autor_usuario_id > 0",
            name=op.f("ck_bitacora_orden_autor_positivo"),
        ),
        sa.CheckConstraint(
            "btrim(descripcion) <> ''",
            name=op.f("ck_bitacora_orden_descripcion_no_vacia"),
        ),
        sa.ForeignKeyConstraint(
            ["orden_id"], ["orden_trabajo.orden_id"],
            name=op.f("fk_bitacora_orden_orden_id_orden_trabajo"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("bitacora_id", name=op.f("pk_bitacora_orden")),
    )
    op.create_index(
        "ix_bitacora_orden_orden_creado",
        "bitacora_orden",
        ["orden_id", "creado_en"],
    )

    # --- REPUESTOS UTILIZADOS EN UNA ACCIÓN ---
    op.create_table(
        "bitacora_repuesto",
        sa.Column("repuesto_bitacora_id", sa.Integer(), nullable=False),
        sa.Column("bitacora_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "btrim(nombre) <> ''",
            name=op.f("ck_bitacora_repuesto_nombre_no_vacio"),
        ),
        sa.CheckConstraint(
            "cantidad > 0",
            name=op.f("ck_bitacora_repuesto_cantidad_positiva"),
        ),
        sa.ForeignKeyConstraint(
            ["bitacora_id"], ["bitacora_orden.bitacora_id"],
            name=op.f("fk_bitacora_repuesto_bitacora_id_bitacora_orden"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "repuesto_bitacora_id", name=op.f("pk_bitacora_repuesto")
        ),
    )
    op.create_index(
        op.f("ix_bitacora_repuesto_bitacora_id"),
        "bitacora_repuesto",
        ["bitacora_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_bitacora_repuesto_bitacora_id"), table_name="bitacora_repuesto"
    )
    op.drop_table("bitacora_repuesto")
    op.drop_index("ix_bitacora_orden_orden_creado", table_name="bitacora_orden")
    op.drop_table("bitacora_orden")
