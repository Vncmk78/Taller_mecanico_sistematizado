"""Solicitudes de nueva atención y unicidad del antecedente vigente.

Revision ID: 0014_nueva_atencion_ms2
Revises: 0013_orden_activa_ms2
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_nueva_atencion_ms2"
down_revision = "0013_orden_activa_ms2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solicitud_nueva_atencion",
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("orden_cancelada_id", sa.Integer(), nullable=False),
        sa.Column("vehiculo_id", sa.Integer(), nullable=False),
        sa.Column("cliente_usuario_id", sa.Integer(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("solicitada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("situacion", sa.String(12), server_default="pendiente", nullable=False),
        sa.Column("respuesta", sa.Text(), nullable=True),
        sa.Column("revisor_id", sa.Integer(), nullable=True),
        sa.Column("revisada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("orden_generada_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("solicitud_id", name=op.f("pk_solicitud_nueva_atencion")),
        sa.ForeignKeyConstraint(["orden_cancelada_id"], ["orden_trabajo.orden_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vehiculo_id"], ["vehiculo.vehiculo_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["orden_generada_id"], ["orden_trabajo.orden_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("cliente_usuario_id > 0", name=op.f("ck_solicitud_nueva_atencion_cliente_positivo")),
        sa.CheckConstraint("revisor_id is null or revisor_id > 0", name=op.f("ck_solicitud_nueva_atencion_revisor_positivo")),
        sa.CheckConstraint("btrim(descripcion) <> '' and length(descripcion) <= 2000", name=op.f("ck_solicitud_nueva_atencion_descripcion_valida")),
        sa.CheckConstraint("situacion in ('pendiente', 'aceptada', 'rechazada')", name=op.f("ck_solicitud_nueva_atencion_situacion_valida")),
        sa.CheckConstraint(
            "(situacion = 'pendiente' and respuesta is null and revisor_id is null and revisada_en is null) "
            "or (situacion in ('aceptada', 'rechazada') and respuesta is not null "
            "and btrim(respuesta) <> '' and revisor_id is not null and revisada_en is not null)",
            name=op.f("ck_solicitud_nueva_atencion_revision_coherente"),
        ),
        sa.CheckConstraint("revisada_en is null or revisada_en >= solicitada_en", name=op.f("ck_solicitud_nueva_atencion_fecha_revision_coherente")),
        sa.CheckConstraint(
            "orden_generada_id is null or (situacion = 'aceptada' and orden_generada_id <> orden_cancelada_id)",
            name=op.f("ck_solicitud_nueva_atencion_orden_generada_coherente"),
        ),
    )
    op.create_index(
        "uq_nueva_atencion_vigente_por_orden", "solicitud_nueva_atencion", ["orden_cancelada_id"],
        unique=True, postgresql_where=sa.text("situacion <> 'rechazada'"),
        sqlite_where=sa.text("situacion <> 'rechazada'"),
    )
    op.create_index(
        "ix_nueva_atencion_cliente_fecha", "solicitud_nueva_atencion",
        ["cliente_usuario_id", "solicitada_en", "solicitud_id"],
    )
    for campo in ("orden_cancelada_id", "vehiculo_id", "orden_generada_id"):
        op.create_index(f"ix_solicitud_nueva_atencion_{campo}", "solicitud_nueva_atencion", [campo])


def downgrade() -> None:
    for campo in ("orden_cancelada_id", "vehiculo_id", "orden_generada_id"):
        op.drop_index(f"ix_solicitud_nueva_atencion_{campo}", table_name="solicitud_nueva_atencion")
    op.drop_index("ix_nueva_atencion_cliente_fecha", table_name="solicitud_nueva_atencion")
    op.drop_index("uq_nueva_atencion_vigente_por_orden", table_name="solicitud_nueva_atencion")
    op.drop_table("solicitud_nueva_atencion")
