"""Restricciones, índices y patente única (Semana 2) — MS2

Revision ID: 0002_ms2
Revises: 0001_ms2
Create Date: 2026-09-19

Endurece el esquema de MS2 sobre la base creada en 0001_ms2 (INT-15, Semana 2):

- Patente ÚNICA de verdad e insensible a mayúsculas/minúsculas: se reemplaza la
  restricción UNIQUE simple (sensible a mayúsculas) por un índice ÚNICO FUNCIONAL
  sobre `upper(patente)`. Así "abcd12" y "ABCD12" se consideran la misma patente y
  no pueden coexistir. El índice sirve además para búsquedas normalizadas.
- CHECKs que protegen la integridad de los datos independientemente del ORM:
  formato de patente (largo razonable, sin espacios sobrantes), año en rango,
  kilometraje no negativo y usuario_id lógico positivo.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# identificadores de la revisión, usados por Alembic.
revision: str = "0002_ms2"
down_revision: Union[str, None] = "0001_ms2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- PATENTE ÚNICA CASE-INSENSITIVE ---
    # Se reemplaza la UNIQUE simple (sensible a mayúsculas) por un índice único
    # funcional sobre upper(patente). create_index no expresa funciones por lista
    # de columnas, así que el índice funcional se crea con SQL explícito.
    op.drop_constraint("uq_vehiculo_patente", "vehiculo", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_vehiculo_patente ON vehiculo (upper(patente))"
    )

    # --- CHECKS DE VEHICULO ---
    # El nombre se pasa SIN prefijo: la convención de nombres (shared/db.py) lo
    # antepone → ck_vehiculo_patente_formato, etc. Así coincide con el nombre que
    # declaran los modelos en __table_args__.
    op.create_check_constraint(
        "patente_formato",
        "vehiculo",
        "char_length(btrim(patente)) between 5 and 10 and patente = upper(btrim(patente))",
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

    # --- CHECK DE CLIENTE ---
    # usuario_id es una referencia lógica a MS1; debe ser un id positivo.
    op.create_check_constraint(
        "usuario_id_positivo",
        "cliente",
        "usuario_id > 0",
    )


def downgrade() -> None:
    # Se dropean por el nombre final ya prefijado por la convención.
    op.drop_constraint("ck_cliente_usuario_id_positivo", "cliente", type_="check")
    op.drop_constraint("ck_vehiculo_km_no_negativo", "vehiculo", type_="check")
    op.drop_constraint("ck_vehiculo_anio_valido", "vehiculo", type_="check")
    op.drop_constraint("ck_vehiculo_patente_formato", "vehiculo", type_="check")
    op.drop_index("uq_vehiculo_patente", table_name="vehiculo")
    op.create_unique_constraint("uq_vehiculo_patente", "vehiculo", ["patente"])
