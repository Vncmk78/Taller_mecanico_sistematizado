"""Avisos transversales: referencias lógicas y outbox propia. Sin reparación histórica."""

from alembic import op
import sqlalchemy as sa

revision = "0008_contexto_avisos_ms1"
down_revision = "0007_canales_notificacion_ms1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notificacion", sa.Column("solicitud_id", sa.Integer(), nullable=True))
    op.add_column("notificacion", sa.Column("presupuesto_id", sa.Integer(), nullable=True))
    op.add_column("notificacion", sa.Column("repuesto_id", sa.Integer(), nullable=True))
    op.alter_column("notificacion", "orden_id", existing_type=sa.INTEGER(), nullable=True)
    op.alter_column("notificacion", "vehiculo_id", existing_type=sa.INTEGER(), nullable=True)


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM notificacion WHERE orden_id IS NULL OR vehiculo_id IS NULL")
    ):
        raise RuntimeError(
            "Hay avisos sin orden o vehículo; el downgrade se detiene sin borrarlos."
        )
    op.alter_column("notificacion", "vehiculo_id", existing_type=sa.INTEGER(), nullable=False)
    op.alter_column("notificacion", "orden_id", existing_type=sa.INTEGER(), nullable=False)
    op.drop_column("notificacion", "repuesto_id")
    op.drop_column("notificacion", "presupuesto_id")
    op.drop_column("notificacion", "solicitud_id")
