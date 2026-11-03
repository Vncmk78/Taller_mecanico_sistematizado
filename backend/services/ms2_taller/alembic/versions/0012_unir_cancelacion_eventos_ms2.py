"""Une cancelación/bitácora con outbox y disponibilidad de MS2.

Revision ID: 0012_integracion_ms2
Revises: 0011_ms2, 0011_disponibilidad_repuestos_ms2

No cambia tablas ni reescribe historial. Alembic aplica los dos antecesores
conservando las revisiones ya utilizadas por MartinH y Develop.
"""

revision = "0012_integracion_ms2"
down_revision = ("0011_ms2", "0011_disponibilidad_repuestos_ms2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
