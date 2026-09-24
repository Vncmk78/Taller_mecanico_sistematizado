"""Auditoría de cambios de umbral de stock (Semana 3) — MS3

Revision ID: 0002_ms3
Revises: 0001_ms3
Create Date: 2026-09-23

Crea historial_umbral: cada cambio del umbral general (repuesto_id vacío) o de
un umbral particular guarda valor anterior, valor nuevo, administrador
responsable (REF lógica a MS1, sin FK, §8), fecha/hora y observación (§4.6).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0002_ms3"
down_revision: Union[str, None] = "0001_ms3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historial_umbral",
        sa.Column("historial_id", sa.Integer(), nullable=False),
        # Vacío = cambio del umbral general.
        sa.Column("repuesto_id", sa.Integer(), nullable=True),
        sa.Column("valor_anterior", sa.Integer(), nullable=True),
        sa.Column("valor_nuevo", sa.Integer(), nullable=True),
        sa.Column("administrador_id", sa.Integer(), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "repuesto_id is not null or valor_nuevo is not null",
            name=op.f("ck_historial_umbral_general_requiere_valor"),
        ),
        sa.CheckConstraint(
            "(valor_anterior is null or valor_anterior >= 0) "
            "and (valor_nuevo is null or valor_nuevo >= 0)",
            name=op.f("ck_historial_umbral_valores_no_negativos"),
        ),
        sa.CheckConstraint(
            "valor_anterior is distinct from valor_nuevo",
            name=op.f("ck_historial_umbral_cambio_real"),
        ),
        sa.CheckConstraint(
            "administrador_id > 0",
            name=op.f("ck_historial_umbral_administrador_positivo"),
        ),
        sa.CheckConstraint(
            "observacion is null or btrim(observacion) <> ''",
            name=op.f("ck_historial_umbral_observacion_no_vacia"),
        ),
        sa.ForeignKeyConstraint(
            ["repuesto_id"], ["repuesto.repuesto_id"],
            name=op.f("fk_historial_umbral_repuesto_id_repuesto"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("historial_id", name=op.f("pk_historial_umbral")),
    )
    op.create_index(op.f("ix_historial_umbral_repuesto_id"), "historial_umbral", ["repuesto_id"])
    op.create_index(op.f("ix_historial_umbral_fecha_hora"), "historial_umbral", ["fecha_hora"])


def downgrade() -> None:
    op.drop_index(op.f("ix_historial_umbral_fecha_hora"), table_name="historial_umbral")
    op.drop_index(op.f("ix_historial_umbral_repuesto_id"), table_name="historial_umbral")
    op.drop_table("historial_umbral")
