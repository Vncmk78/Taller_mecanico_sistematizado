"""Dispositivos, entregas por canal e intentos de MS1.

No reencola notificaciones históricas ni modifica credenciales de usuario.
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_canales_notificacion_ms1"
down_revision = "0006_lectura_notificaciones_ms1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dispositivo_push",
        sa.Column("dispositivo_id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("plataforma", sa.String(length=20), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.usuario_id"],
            name=op.f("fk_dispositivo_push_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dispositivo_id", name=op.f("pk_dispositivo_push")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_dispositivo_push_token_hash")),
    )
    op.create_index(
        op.f("ix_dispositivo_push_usuario_id"), "dispositivo_push", ["usuario_id"], unique=False
    )
    op.create_table(
        "entrega_notificacion",
        sa.Column("entrega_id", sa.Integer(), nullable=False),
        sa.Column("notificacion_id", sa.Integer(), nullable=False),
        sa.Column("dispositivo_id", sa.Uuid(), nullable=True),
        sa.Column("clave", sa.String(length=150), nullable=False),
        sa.Column("canal", sa.String(length=10), nullable=False),
        sa.Column("estado", sa.String(length=24), server_default="pendiente", nullable=False),
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "proxima_tentativa_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aceptada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_error", sa.String(length=80), nullable=True),
        sa.Column("proveedor_id", sa.String(length=300), nullable=True),
        sa.CheckConstraint(
            "canal IN ('correo','push')", name=op.f("ck_entrega_notificacion_canal_valido")
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente','procesando','aceptada','fallida','sin_configuracion','sin_dispositivo','omitida')",
            name=op.f("ck_entrega_notificacion_estado_entrega_valido"),
        ),
        sa.CheckConstraint(
            "intentos >= 0", name=op.f("ck_entrega_notificacion_intentos_entrega_no_negativos")
        ),
        sa.ForeignKeyConstraint(
            ["dispositivo_id"],
            ["dispositivo_push.dispositivo_id"],
            name=op.f("fk_entrega_notificacion_dispositivo_id_dispositivo_push"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["notificacion_id"],
            ["notificacion.notificacion_id"],
            name=op.f("fk_entrega_notificacion_notificacion_id_notificacion"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("entrega_id", name=op.f("pk_entrega_notificacion")),
        sa.UniqueConstraint("clave", name=op.f("uq_entrega_notificacion_clave")),
    )
    op.create_index(
        op.f("ix_entrega_notificacion_dispositivo_id"),
        "entrega_notificacion",
        ["dispositivo_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_entrega_notificacion_notificacion_id"),
        "entrega_notificacion",
        ["notificacion_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_entrega_notificacion_proxima_tentativa_en"),
        "entrega_notificacion",
        ["proxima_tentativa_en"],
        unique=False,
    )
    op.create_table(
        "intento_entrega",
        sa.Column("intento_id", sa.Integer(), nullable=False),
        sa.Column("entrega_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column(
            "iniciado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finalizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resultado", sa.String(length=24), server_default="procesando", nullable=False),
        sa.Column("codigo_error", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["entrega_id"],
            ["entrega_notificacion.entrega_id"],
            name=op.f("fk_intento_entrega_entrega_id_entrega_notificacion"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("intento_id", name=op.f("pk_intento_entrega")),
        sa.UniqueConstraint("entrega_id", "numero", name="uq_intento_entrega_numero"),
    )
    op.create_index(
        op.f("ix_intento_entrega_entrega_id"), "intento_entrega", ["entrega_id"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_intento_entrega_entrega_id"), table_name="intento_entrega")
    op.drop_table("intento_entrega")
    op.drop_index(
        op.f("ix_entrega_notificacion_proxima_tentativa_en"), table_name="entrega_notificacion"
    )
    op.drop_index(
        op.f("ix_entrega_notificacion_notificacion_id"), table_name="entrega_notificacion"
    )
    op.drop_index(op.f("ix_entrega_notificacion_dispositivo_id"), table_name="entrega_notificacion")
    op.drop_table("entrega_notificacion")
    op.drop_index(op.f("ix_dispositivo_push_usuario_id"), table_name="dispositivo_push")
    op.drop_table("dispositivo_push")
