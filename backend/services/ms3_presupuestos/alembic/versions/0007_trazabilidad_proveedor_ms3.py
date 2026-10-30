"""Trazabilidad Repuesto–Proveedor/Distribuidor — MS3.

Revision ID: 0007_ms3
Revises: 0006_ms3

Semana 7 · "Implementar trazabilidad Repuesto–Proveedor/Distribuidor".

1. proveedor.tipo_distribuidor: "oficial" o "generico" (los existentes quedan
   como "generico"; el administrador corrige los que sean oficiales).
2. historial_proveedor_repuesto: alta y cada cambio de proveedor de un
   repuesto. A cada repuesto existente se le registra su proveedor actual
   (registrado_por_id vacío = fila creada por esta migración). Si se borra un
   repuesto (solo se permite si nunca se usó) su historial se va con él;
   un proveedor referenciado en el historial no se puede borrar (RESTRICT).
3. movimiento_inventario.proveedor_id: qué proveedor entregó las unidades de
   cada ingreso. Los ingresos existentes toman el proveedor actual del
   repuesto (es lo único que se sabía); los demás tipos no llevan proveedor.

Todo es aditivo: no borra datos. El downgrade quita lo agregado.
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_ms3"
down_revision = "0006_ms3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Tipo de distribuidor.
    op.add_column("proveedor", sa.Column(
        "tipo_distribuidor", sa.String(length=10), nullable=False, server_default="generico"))
    op.create_check_constraint(
        op.f("ck_proveedor_tipo_distribuidor_valido"), "proveedor", "tipo_distribuidor in ('oficial', 'generico')")

    # 2) Historial de proveedores de cada repuesto.
    op.create_table(
        "historial_proveedor_repuesto",
        sa.Column("historial_id", sa.Integer(), nullable=False),
        sa.Column("repuesto_id", sa.Integer(), nullable=False),
        sa.Column("proveedor_anterior_id", sa.Integer(), nullable=True),
        sa.Column("proveedor_nuevo_id", sa.Integer(), nullable=False),
        sa.Column("registrado_por_id", sa.Integer(), nullable=True),
        sa.Column("observacion", sa.String(length=500), nullable=True),
        sa.Column("fecha_hora", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.CheckConstraint(
            "proveedor_anterior_id is null or proveedor_anterior_id <> proveedor_nuevo_id",
            name=op.f("ck_historial_proveedor_repuesto_cambio_real")),
        sa.CheckConstraint(
            "registrado_por_id is null or registrado_por_id > 0",
            name=op.f("ck_historial_proveedor_repuesto_registrado_por_positivo")),
        sa.ForeignKeyConstraint(
            ["repuesto_id"], ["repuesto.repuesto_id"], ondelete="CASCADE",
            name=op.f("fk_historial_proveedor_repuesto_repuesto_id_repuesto")),
        sa.ForeignKeyConstraint(
            ["proveedor_anterior_id"], ["proveedor.proveedor_id"], ondelete="RESTRICT",
            name=op.f("fk_historial_proveedor_repuesto_proveedor_anterior_id_proveedor")),
        sa.ForeignKeyConstraint(
            ["proveedor_nuevo_id"], ["proveedor.proveedor_id"], ondelete="RESTRICT",
            name=op.f("fk_historial_proveedor_repuesto_proveedor_nuevo_id_proveedor")),
        sa.PrimaryKeyConstraint("historial_id", name=op.f("pk_historial_proveedor_repuesto")),
    )
    op.create_index("ix_historial_proveedor_repuesto_repuesto", "historial_proveedor_repuesto",
                    ["repuesto_id", "fecha_hora"])
    op.create_index(op.f("ix_historial_proveedor_repuesto_proveedor_anterior_id"),
                    "historial_proveedor_repuesto", ["proveedor_anterior_id"])
    op.create_index(op.f("ix_historial_proveedor_repuesto_proveedor_nuevo_id"),
                    "historial_proveedor_repuesto", ["proveedor_nuevo_id"])
    op.execute(
        "INSERT INTO historial_proveedor_repuesto (repuesto_id, proveedor_nuevo_id, observacion) "
        "SELECT repuesto_id, proveedor_id, 'Proveedor vigente al habilitar la trazabilidad' "
        "FROM repuesto"
    )

    # 3) Proveedor de cada ingreso.
    op.add_column("movimiento_inventario", sa.Column("proveedor_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_movimiento_inventario_proveedor_id_proveedor"), "movimiento_inventario",
        "proveedor", ["proveedor_id"], ["proveedor_id"], ondelete="RESTRICT")
    op.create_index(op.f("ix_movimiento_inventario_proveedor_id"), "movimiento_inventario",
                    ["proveedor_id"])
    op.execute(
        "UPDATE movimiento_inventario m SET proveedor_id = r.proveedor_id "
        "FROM repuesto r WHERE r.repuesto_id = m.repuesto_id AND m.tipo = 'ingreso'"
    )
    op.create_check_constraint(
        op.f("ck_movimiento_inventario_proveedor_solo_en_ingreso"), "movimiento_inventario",
        "(tipo = 'ingreso' and proveedor_id is not null) or "
        "(tipo <> 'ingreso' and proveedor_id is null)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_movimiento_inventario_proveedor_solo_en_ingreso"),
                       "movimiento_inventario", type_="check")
    op.drop_index(op.f("ix_movimiento_inventario_proveedor_id"), table_name="movimiento_inventario")
    op.drop_constraint(op.f("fk_movimiento_inventario_proveedor_id_proveedor"),
                       "movimiento_inventario", type_="foreignkey")
    op.drop_column("movimiento_inventario", "proveedor_id")
    op.drop_table("historial_proveedor_repuesto")
    op.drop_constraint(op.f("ck_proveedor_tipo_distribuidor_valido"), "proveedor", type_="check")
    op.drop_column("proveedor", "tipo_distribuidor")
