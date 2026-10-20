"""Configuración y auditoría de capacidad activa por mecánico.

Revision ID: 0008_ms2
Revises: 0007_ms2
"""
from alembic import op
import sqlalchemy as sa


revision = "0008_ms2"
down_revision = "0007_ms2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configuracion_capacidad_mecanico",
        sa.Column("configuracion_id", sa.Integer(), primary_key=True),
        sa.Column("max_ordenes_activas", sa.Integer(), nullable=True),
        sa.Column("actualizado_por_id", sa.Integer(), nullable=True),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("configuracion_id = 1", name="singleton"),
        sa.CheckConstraint(
            "max_ordenes_activas is null or max_ordenes_activas > 0",
            name="maximo_positivo",
        ),
        sa.CheckConstraint(
            "actualizado_por_id is null or actualizado_por_id > 0",
            name="administrador_positivo",
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO configuracion_capacidad_mecanico "
            "(configuracion_id, max_ordenes_activas, actualizado_por_id) "
            "VALUES (1, NULL, NULL)"
        )
    )
    op.create_table(
        "historial_configuracion_capacidad_mecanico",
        sa.Column("historial_id", sa.Integer(), primary_key=True),
        sa.Column("valor_anterior", sa.Integer(), nullable=True),
        sa.Column("valor_nuevo", sa.Integer(), nullable=False),
        sa.Column("administrador_id", sa.Integer(), nullable=False),
        sa.Column(
            "fecha_hora",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "valor_nuevo > 0 and administrador_id > 0 "
            "and (valor_anterior is null or "
            "(valor_anterior > 0 and valor_anterior <> valor_nuevo))",
            name="valores_positivos",
        ),
    )
    op.create_table(
        "historial_validacion_capacidad_mecanico",
        sa.Column("validacion_id", sa.Integer(), primary_key=True),
        sa.Column(
            "orden_id",
            sa.Integer(),
            sa.ForeignKey("orden_trabajo.orden_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("mecanico_anterior_id", sa.Integer(), nullable=True),
        sa.Column("mecanico_id", sa.Integer(), nullable=False),
        sa.Column("administrador_id", sa.Integer(), nullable=False),
        sa.Column("ordenes_activas", sa.Integer(), nullable=False),
        sa.Column("max_ordenes_activas", sa.Integer(), nullable=True),
        sa.Column("aceptada", sa.Boolean(), nullable=False),
        sa.Column("resultado", sa.String(length=40), nullable=False),
        sa.Column(
            "fecha_hora",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "orden_id > 0 and mecanico_id > 0 and administrador_id > 0 "
            "and ordenes_activas >= 0 "
            "and (max_ordenes_activas is null or max_ordenes_activas > 0) "
            "and (mecanico_anterior_id is null or mecanico_anterior_id > 0) "
            "and ((aceptada and resultado = 'capacidad_disponible') or "
            "(not aceptada and resultado in "
            "('capacidad_excedida', 'capacidad_no_configurada')))",
            name="datos_validos",
        ),
    )
    op.create_index(
        "ix_orden_mecanico_estado",
        "orden_trabajo",
        ["mecanico_actual_id", "estado_codigo"],
    )
    op.create_index(
        "ix_validacion_capacidad_orden_fecha",
        "historial_validacion_capacidad_mecanico",
        ["orden_id", "fecha_hora"],
    )
    op.create_index(
        "ix_validacion_capacidad_mecanico_fecha",
        "historial_validacion_capacidad_mecanico",
        ["mecanico_id", "fecha_hora"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_validacion_capacidad_mecanico_fecha",
        table_name="historial_validacion_capacidad_mecanico",
    )
    op.drop_index(
        "ix_validacion_capacidad_orden_fecha",
        table_name="historial_validacion_capacidad_mecanico",
    )
    op.drop_index("ix_orden_mecanico_estado", table_name="orden_trabajo")
    op.drop_table("historial_validacion_capacidad_mecanico")
    op.drop_table("historial_configuracion_capacidad_mecanico")
    op.drop_table("configuracion_capacidad_mecanico")
