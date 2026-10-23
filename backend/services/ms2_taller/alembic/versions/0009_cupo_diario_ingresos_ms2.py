"""Configuración y auditoría del cupo diario de ingresos físicos.

Revision ID: 0009_ms2
Revises: 0008_ms2
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_ms2"
down_revision = "0008_ms2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_ingreso_vehiculo_fecha_hora", "ingreso_vehiculo", ["fecha_hora"]
    )
    op.create_table(
        "configuracion_cupo_ingresos",
        sa.Column("configuracion_id", sa.Integer(), primary_key=True),
        sa.Column("max_ingresos_diarios", sa.Integer(), nullable=True),
        sa.Column("actualizado_por_id", sa.Integer(), nullable=True),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("configuracion_id = 1", name="singleton"),
        sa.CheckConstraint(
            "max_ingresos_diarios is null or max_ingresos_diarios > 0",
            name="maximo_positivo",
        ),
        sa.CheckConstraint(
            "actualizado_por_id is null or actualizado_por_id > 0",
            name="administrador_positivo",
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO configuracion_cupo_ingresos "
            "(configuracion_id, max_ingresos_diarios, actualizado_por_id) "
            "VALUES (1, NULL, NULL)"
        )
    )
    op.create_table(
        "historial_configuracion_cupo_ingresos",
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
        "historial_validacion_cupo_ingreso",
        sa.Column("validacion_id", sa.Integer(), primary_key=True),
        sa.Column(
            "vehiculo_id",
            sa.Integer(),
            sa.ForeignKey("vehiculo.vehiculo_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "ingreso_id",
            sa.Integer(),
            sa.ForeignKey("ingreso_vehiculo.ingreso_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("jornada_local", sa.Date(), nullable=False),
        sa.Column("ingresos_registrados", sa.Integer(), nullable=False),
        sa.Column("max_ingresos_diarios", sa.Integer(), nullable=True),
        sa.Column("administrador_id", sa.Integer(), nullable=False),
        sa.Column("aceptada", sa.Boolean(), nullable=False),
        sa.Column("resultado", sa.String(length=40), nullable=False),
        sa.Column(
            "fecha_hora",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "vehiculo_id > 0 and administrador_id > 0 and ingresos_registrados >= 0 "
            "and (max_ingresos_diarios is null or max_ingresos_diarios > 0) "
            "and (ingreso_id is null or ingreso_id > 0) "
            "and ((aceptada and resultado = 'cupo_disponible' and ingreso_id is not null) "
            "or (not aceptada and resultado in "
            "('cupo_excedido', 'cupo_no_configurado') and ingreso_id is null))",
            name="datos_validos",
        ),
    )
    op.create_index(
        "ix_validacion_cupo_jornada",
        "historial_validacion_cupo_ingreso",
        ["jornada_local", "fecha_hora"],
    )
    op.create_index(
        "ix_validacion_cupo_vehiculo",
        "historial_validacion_cupo_ingreso",
        ["vehiculo_id", "fecha_hora"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_validacion_cupo_vehiculo",
        table_name="historial_validacion_cupo_ingreso",
    )
    op.drop_index(
        "ix_validacion_cupo_jornada",
        table_name="historial_validacion_cupo_ingreso",
    )
    op.drop_table("historial_validacion_cupo_ingreso")
    op.drop_table("historial_configuracion_cupo_ingresos")
    op.drop_table("configuracion_cupo_ingresos")
    op.drop_index(
        "ix_ingreso_vehiculo_fecha_hora", table_name="ingreso_vehiculo"
    )
