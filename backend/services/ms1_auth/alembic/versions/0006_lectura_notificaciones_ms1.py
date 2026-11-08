"""Estado de lectura persistente de los avisos personales.

Revision ID: 0006_lectura_notificaciones_ms1
Revises: 0005_integracion_ms1
"""
from alembic import op
import sqlalchemy as sa
revision = "0006_lectura_notificaciones_ms1"
down_revision = "0005_integracion_ms1"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("notificacion", sa.Column("leida", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("notificacion", sa.Column("leida_en", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column("notificacion", "leida_en")
    op.drop_column("notificacion", "leida")
