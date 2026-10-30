"""Solicitud y confirmación administrativa de cancelación — MS2.

Revision ID: 0011_ms2
Revises: 0010_ms2
"""
from alembic import op
import sqlalchemy as sa


revision = "0011_ms2"
down_revision = "0010_ms2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solicitud_cancelacion",
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("cliente_usuario_id", sa.Integer(), nullable=False),
        sa.Column("estado_al_solicitar", sa.SmallInteger(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(length=12), server_default="pendiente", nullable=False),
        sa.Column("solicitada_en", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("administrador_id", sa.Integer(), nullable=True),
        sa.Column("confirmada_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("cliente_usuario_id > 0",
                           name=op.f("ck_solicitud_cancelacion_cliente_positivo")),
        sa.CheckConstraint("administrador_id is null or administrador_id > 0",
                           name=op.f("ck_solicitud_cancelacion_administrador_positivo")),
        sa.CheckConstraint("estado_al_solicitar in (1, 2, 3)",
                           name=op.f("ck_solicitud_cancelacion_estado_cancelable")),
        sa.CheckConstraint("estado in ('pendiente', 'confirmada')",
                           name=op.f("ck_solicitud_cancelacion_estado_valido")),
        sa.CheckConstraint(
            "(estado = 'pendiente' and administrador_id is null and confirmada_en is null) "
            "or (estado = 'confirmada' and administrador_id is not null "
            "and confirmada_en is not null)",
            name=op.f("ck_solicitud_cancelacion_confirmacion_coherente"),
        ),
        sa.CheckConstraint("btrim(motivo) <> ''",
                           name=op.f("ck_solicitud_cancelacion_motivo_no_vacio")),
        sa.ForeignKeyConstraint(["orden_id"], ["orden_trabajo.orden_id"],
                                ondelete="RESTRICT",
                                name=op.f("fk_solicitud_cancelacion_orden_id_orden_trabajo")),
        sa.PrimaryKeyConstraint("solicitud_id", name=op.f("pk_solicitud_cancelacion")),
        sa.UniqueConstraint("orden_id", name=op.f("uq_solicitud_cancelacion_orden")),
    )


def downgrade() -> None:
    op.drop_table("solicitud_cancelacion")
