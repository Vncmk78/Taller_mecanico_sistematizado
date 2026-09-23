"""Inicial MS3: presupuestos, repuestos, proveedores e inventario

Revision ID: 0001_ms3
Revises:
Create Date: 2026-09-23

Primera migración del microservicio MS3 según el MER (recuadro "BD MS3"):

- proveedor y repuesto (1:N), con stock y umbral particular no negativos.
- parametro_inventario: umbral general con vigencia (uno solo vigente).
- movimiento_inventario: cada cambio de stock, con clave de operación única.
- presupuesto (uno por orden), version_presupuesto (numerada) e
  item_presupuesto (repuesto o mano de obra).

Las referencias a órdenes (MS2) y usuarios (MS1) son columnas sin FK (§8).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0001_ms3"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- PROVEEDOR ---
    op.create_table("proveedor",
    sa.Column("proveedor_id", sa.Integer(), nullable=False),
    sa.Column("nombre", sa.String(length=120), nullable=False),
    sa.Column("contacto", sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint("proveedor_id", name=op.f("pk_proveedor")),
    sa.UniqueConstraint("nombre", name=op.f("uq_proveedor_nombre"))
    )

    # --- REPUESTO (stock y umbral particular, §4.6) ---
    op.create_table("repuesto",
    sa.Column("repuesto_id", sa.Integer(), nullable=False),
    sa.Column("proveedor_id", sa.Integer(), nullable=False),
    sa.Column("nombre", sa.String(length=120), nullable=False),
    sa.Column("stock", sa.Integer(), server_default="0", nullable=False),
    sa.Column("umbral_particular", sa.Integer(), nullable=True),
    sa.CheckConstraint("stock >= 0", name=op.f("ck_repuesto_stock_no_negativo")),
    sa.CheckConstraint("umbral_particular is null or umbral_particular >= 0", name=op.f("ck_repuesto_umbral_no_negativo")),
    sa.ForeignKeyConstraint(["proveedor_id"], ["proveedor.proveedor_id"], name=op.f("fk_repuesto_proveedor_id_proveedor"), ondelete="RESTRICT"),
    sa.PrimaryKeyConstraint("repuesto_id", name=op.f("pk_repuesto"))
    )
    op.create_index(op.f("ix_repuesto_proveedor_id"), "repuesto", ["proveedor_id"], unique=False)

    # --- PARÁMETRO DE INVENTARIO (umbral general con vigencia) ---
    # Índice único PARCIAL: un solo parámetro vigente (vigente_hasta vacío).
    op.create_table("parametro_inventario",
    sa.Column("parametro_id", sa.Integer(), nullable=False),
    sa.Column("umbral_general", sa.Integer(), nullable=False),
    sa.Column("actualizado_por_id", sa.Integer(), nullable=False),
    sa.Column("vigente_desde", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("actualizado_por_id > 0", name=op.f("ck_parametro_inventario_actualizado_por_positivo")),
    sa.CheckConstraint("umbral_general >= 0", name=op.f("ck_parametro_inventario_umbral_no_negativo")),
    sa.CheckConstraint("vigente_hasta is null or vigente_hasta > vigente_desde", name=op.f("ck_parametro_inventario_vigencia_valida")),
    sa.PrimaryKeyConstraint("parametro_id", name=op.f("pk_parametro_inventario"))
    )
    op.create_index("uq_parametro_inventario_vigente", "parametro_inventario", [sa.literal_column("(vigente_hasta is null)")], unique=True, postgresql_where=sa.text("vigente_hasta is null"))

    # --- MOVIMIENTO DE INVENTARIO (auditoría de stock, §4.6) ---
    # clave_operacion UK: evita registrar dos veces la misma operación.
    # orden_id y registrado_por_id son REF lógicas a MS2/MS1, sin FK (§8).
    op.create_table("movimiento_inventario",
    sa.Column("movimiento_id", sa.Integer(), nullable=False),
    sa.Column("clave_operacion", sa.String(length=80), nullable=False),
    sa.Column("repuesto_id", sa.Integer(), nullable=False),
    sa.Column("orden_id", sa.Integer(), nullable=True),
    sa.Column("tipo", sa.String(length=12), nullable=False),
    sa.Column("cantidad", sa.Integer(), nullable=False),
    sa.Column("fecha_hora", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("registrado_por_id", sa.Integer(), nullable=False),
    sa.CheckConstraint("(tipo = 'ajuste' and cantidad <> 0) or (tipo <> 'ajuste' and cantidad > 0)", name=op.f("ck_movimiento_inventario_cantidad_valida")),
    sa.CheckConstraint("tipo in ('compromiso', 'consumo', 'liberacion', 'ajuste', 'ingreso')", name=op.f("ck_movimiento_inventario_tipo_valido")),
    sa.CheckConstraint("tipo not in ('compromiso', 'consumo', 'liberacion') or orden_id is not null", name=op.f("ck_movimiento_inventario_orden_obligatoria")),
    sa.CheckConstraint("orden_id is null or orden_id > 0", name=op.f("ck_movimiento_inventario_orden_positiva")),
    sa.CheckConstraint("registrado_por_id > 0", name=op.f("ck_movimiento_inventario_registrado_por_positivo")),
    sa.ForeignKeyConstraint(["repuesto_id"], ["repuesto.repuesto_id"], name=op.f("fk_movimiento_inventario_repuesto_id_repuesto"), ondelete="RESTRICT"),
    sa.PrimaryKeyConstraint("movimiento_id", name=op.f("pk_movimiento_inventario")),
    sa.UniqueConstraint("clave_operacion", name=op.f("uq_movimiento_inventario_clave_operacion"))
    )
    op.create_index("ix_movimiento_inventario_orden_id", "movimiento_inventario", ["orden_id"], unique=False)
    op.create_index(op.f("ix_movimiento_inventario_repuesto_id"), "movimiento_inventario", ["repuesto_id"], unique=False)

    # --- PRESUPUESTO (uno por orden, §4.3) ---
    # orden_id: REF lógica a MS2, única y sin FK física (§8).
    op.create_table("presupuesto",
    sa.Column("presupuesto_id", sa.Integer(), nullable=False),
    sa.Column("orden_id", sa.Integer(), nullable=False),
    sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.CheckConstraint("orden_id > 0", name=op.f("ck_presupuesto_orden_positiva")),
    sa.PrimaryKeyConstraint("presupuesto_id", name=op.f("pk_presupuesto")),
    sa.UniqueConstraint("orden_id", name=op.f("uq_presupuesto_orden_id"))
    )

    # --- VERSIÓN DE PRESUPUESTO ---
    op.create_table("version_presupuesto",
    sa.Column("version_id", sa.Integer(), nullable=False),
    sa.Column("presupuesto_id", sa.Integer(), nullable=False),
    sa.Column("numero", sa.Integer(), nullable=False),
    sa.Column("creado_por_id", sa.Integer(), nullable=False),
    sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("enviado_en", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("creado_por_id > 0", name=op.f("ck_version_presupuesto_creado_por_positivo")),
    sa.CheckConstraint("enviado_en is null or enviado_en >= creado_en", name=op.f("ck_version_presupuesto_envio_posterior")),
    sa.CheckConstraint("numero >= 1", name=op.f("ck_version_presupuesto_numero_positivo")),
    sa.ForeignKeyConstraint(["presupuesto_id"], ["presupuesto.presupuesto_id"], name=op.f("fk_version_presupuesto_presupuesto_id_presupuesto"), ondelete="RESTRICT"),
    sa.PrimaryKeyConstraint("version_id", name=op.f("pk_version_presupuesto")),
    sa.UniqueConstraint("presupuesto_id", "numero", name=op.f("uq_version_presupuesto_presupuesto_id"))
    )

    # --- ÍTEM DE PRESUPUESTO (repuesto o mano de obra) ---
    op.create_table("item_presupuesto",
    sa.Column("item_id", sa.Integer(), nullable=False),
    sa.Column("version_id", sa.Integer(), nullable=False),
    sa.Column("tipo", sa.String(length=12), nullable=False),
    sa.Column("repuesto_id", sa.Integer(), nullable=True),
    sa.Column("descripcion", sa.String(length=200), nullable=False),
    sa.Column("cantidad", sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column("precio_unitario", sa.Numeric(precision=12, scale=2), nullable=False),
    sa.CheckConstraint("(tipo = 'repuesto') = (repuesto_id is not null)", name=op.f("ck_item_presupuesto_repuesto_segun_tipo")),
    sa.CheckConstraint("tipo in ('repuesto', 'mano_de_obra')", name=op.f("ck_item_presupuesto_tipo_valido")),
    sa.CheckConstraint("cantidad > 0", name=op.f("ck_item_presupuesto_cantidad_positiva")),
    sa.CheckConstraint("precio_unitario >= 0", name=op.f("ck_item_presupuesto_precio_no_negativo")),
    sa.ForeignKeyConstraint(["repuesto_id"], ["repuesto.repuesto_id"], name=op.f("fk_item_presupuesto_repuesto_id_repuesto"), ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["version_id"], ["version_presupuesto.version_id"], name=op.f("fk_item_presupuesto_version_id_version_presupuesto"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("item_id", name=op.f("pk_item_presupuesto"))
    )
    op.create_index(op.f("ix_item_presupuesto_repuesto_id"), "item_presupuesto", ["repuesto_id"], unique=False)
    op.create_index(op.f("ix_item_presupuesto_version_id"), "item_presupuesto", ["version_id"], unique=False)


def downgrade() -> None:
    # Orden inverso a upgrade (primero lo que depende de otras tablas).
    op.drop_index(op.f("ix_movimiento_inventario_repuesto_id"), table_name="movimiento_inventario")
    op.drop_index("ix_movimiento_inventario_orden_id", table_name="movimiento_inventario")
    op.drop_table("movimiento_inventario")
    op.drop_index(op.f("ix_item_presupuesto_version_id"), table_name="item_presupuesto")
    op.drop_index(op.f("ix_item_presupuesto_repuesto_id"), table_name="item_presupuesto")
    op.drop_table("item_presupuesto")
    op.drop_table("version_presupuesto")
    op.drop_index(op.f("ix_repuesto_proveedor_id"), table_name="repuesto")
    op.drop_table("repuesto")
    op.drop_table("proveedor")
    op.drop_table("presupuesto")
    op.drop_index("uq_parametro_inventario_vigente", table_name="parametro_inventario", postgresql_where=sa.text("vigente_hasta is null"))
    op.drop_table("parametro_inventario")
