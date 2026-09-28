"""Regulariza restricciones de vehículo según la fuente funcional.

Revision ID: 0005_ms2
Revises: 0004_ms2
Create Date: 2026-09-27

La sistematización exige que la patente sea obligatoria, no vacía y única, pero
no define formato, largo, normalización a mayúsculas ni rangos para año o
kilometraje. Esta migración forward retira los CHECK no respaldados que agregó
0002_ms2, conserva la integridad documentada y amplía la columna de patente para
que la base no aplique un máximo que el contrato HTTP no puede justificar.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_ms2"
down_revision: Union[str, None] = "0004_ms2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_vehiculo_patente_formato"), "vehiculo", type_="check"
    )
    op.drop_constraint(op.f("ck_vehiculo_anio_valido"), "vehiculo", type_="check")
    op.drop_constraint(op.f("ck_vehiculo_km_no_negativo"), "vehiculo", type_="check")

    op.drop_index("uq_vehiculo_patente", table_name="vehiculo")
    op.alter_column(
        "vehiculo",
        "patente",
        existing_type=sa.String(length=10),
        type_=sa.String(),
        existing_nullable=False,
    )
    op.create_unique_constraint("uq_vehiculo_patente", "vehiculo", ["patente"])
    op.create_check_constraint(
        "patente_no_vacia",
        "vehiculo",
        "length(trim(patente)) > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_vehiculo_patente_no_vacia"), "vehiculo", type_="check"
    )
    op.drop_constraint(op.f("uq_vehiculo_patente"), "vehiculo", type_="unique")
    op.alter_column(
        "vehiculo",
        "patente",
        existing_type=sa.String(),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_vehiculo_patente ON vehiculo (upper(patente))"
    )
    op.create_check_constraint(
        "patente_formato",
        "vehiculo",
        "char_length(btrim(patente)) between 5 and 10 "
        "and patente = upper(btrim(patente))",
    )
    op.create_check_constraint(
        "anio_valido",
        "vehiculo",
        "anio is null or (anio between 1900 and 2100)",
    )
    op.create_check_constraint(
        "km_no_negativo",
        "vehiculo",
        "kilometraje is null or kilometraje >= 0",
    )
