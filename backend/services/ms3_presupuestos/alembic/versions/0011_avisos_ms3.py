"""Avisos transversales: referencias lógicas y outbox propia. Sin reparación histórica."""

from alembic import op
import sqlalchemy as sa

revision = "0011_avisos_ms3"
down_revision = "0010_ms3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evento_aviso_outbox",
        sa.Column("outbox_id", sa.Integer(), nullable=False),
        sa.Column("evento_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "proxima_tentativa_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_error", sa.String(length=300), nullable=True),
        sa.CheckConstraint(
            "intentos >= 0", name=op.f("ck_evento_aviso_outbox_intentos_aviso_no_negativos")
        ),
        sa.PrimaryKeyConstraint("outbox_id", name=op.f("pk_evento_aviso_outbox")),
        sa.UniqueConstraint("evento_id", name=op.f("uq_evento_aviso_outbox_evento_id")),
    )
    op.create_index(
        "ix_evento_aviso_outbox_proxima_tentativa_en",
        "evento_aviso_outbox",
        ["proxima_tentativa_en"],
    )


def downgrade():
    op.drop_table("evento_aviso_outbox")
