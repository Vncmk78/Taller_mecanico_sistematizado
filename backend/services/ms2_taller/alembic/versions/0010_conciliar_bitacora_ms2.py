"""Asegura la bitácora tras integrar historiales de migración divergentes.

Revision ID: 0010_ms2
Revises: 0009_ms2

Las ramas históricas usaron el identificador 0007_ms2 para dos migraciones
distintas. Una base que ya registró el antiguo 0009_ms2 tiene capacidad y cupo,
pero puede carecer de las tablas de bitácora que también usaban 0007_ms2.
Esta migración aditiva repara ese caso y es inocua cuando las tablas ya existen.
No elimina datos al revertirse porque algunas instalaciones ya pueden tener
registros legítimos de bitácora.
"""
from alembic import op
import sqlalchemy as sa


revision = "0010_ms2"
down_revision = "0009_ms2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tablas = set(inspector.get_table_names())
    if "bitacora_orden" not in tablas:
        op.create_table(
            "bitacora_orden",
            sa.Column("bitacora_id", sa.Integer(), nullable=False),
            sa.Column("orden_id", sa.Integer(), nullable=False),
            sa.Column("autor_usuario_id", sa.Integer(), nullable=False),
            sa.Column("tipo", sa.String(length=12), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=False),
            sa.Column("creado_en", sa.DateTime(timezone=True),
                      server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("tipo in ('observacion', 'accion')",
                               name=op.f("ck_bitacora_orden_tipo_valido")),
            sa.CheckConstraint("autor_usuario_id > 0",
                               name=op.f("ck_bitacora_orden_autor_positivo")),
            sa.CheckConstraint("btrim(descripcion) <> ''",
                               name=op.f("ck_bitacora_orden_descripcion_no_vacia")),
            sa.ForeignKeyConstraint(
                ["orden_id"], ["orden_trabajo.orden_id"],
                name=op.f("fk_bitacora_orden_orden_id_orden_trabajo"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("bitacora_id", name=op.f("pk_bitacora_orden")),
        )
        op.create_index("ix_bitacora_orden_orden_creado", "bitacora_orden",
                        ["orden_id", "creado_en"])
    tablas = set(sa.inspect(op.get_bind()).get_table_names())
    if "bitacora_repuesto" not in tablas:
        op.create_table(
            "bitacora_repuesto",
            sa.Column("repuesto_bitacora_id", sa.Integer(), nullable=False),
            sa.Column("bitacora_id", sa.Integer(), nullable=False),
            sa.Column("nombre", sa.String(length=120), nullable=False),
            sa.Column("cantidad", sa.Integer(), nullable=False),
            sa.CheckConstraint("btrim(nombre) <> ''",
                               name=op.f("ck_bitacora_repuesto_nombre_no_vacio")),
            sa.CheckConstraint("cantidad > 0",
                               name=op.f("ck_bitacora_repuesto_cantidad_positiva")),
            sa.ForeignKeyConstraint(
                ["bitacora_id"], ["bitacora_orden.bitacora_id"],
                name=op.f("fk_bitacora_repuesto_bitacora_id_bitacora_orden"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint(
                "repuesto_bitacora_id", name=op.f("pk_bitacora_repuesto")
            ),
        )
        op.create_index(op.f("ix_bitacora_repuesto_bitacora_id"),
                        "bitacora_repuesto", ["bitacora_id"], unique=False)


def downgrade() -> None:
    # La migración puede no haber creado las tablas; eliminarlas podría borrar
    # datos existentes en instalaciones que ya tenían bitácora.
    pass
