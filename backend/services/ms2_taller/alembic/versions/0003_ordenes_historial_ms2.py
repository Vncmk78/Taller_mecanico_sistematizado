"""Órdenes de trabajo e historial de estados (Semana 3) — MS2

Revision ID: 0003_ms2
Revises: 0002_ms2
Create Date: 2026-09-22

Crea las tablas del MER (recuadro "BD MS2") para el ciclo de vida de la orden:

- estado_orden: catálogo de los 8 estados (§4.2), cargado aquí mismo.
- ingreso_vehiculo: estancia física del vehículo; toda orden nace de un ingreso.
- orden_trabajo: la orden, con FK a vehículo, ingreso y estado.
- historial_estado: cada cambio de estado de una orden (quién, cuándo, origen).

Todas las FK son locales a MS2 y RESTRICT (la historia no se borra). Las
referencias a usuarios de MS1 son columnas sueltas, sin FK (§8).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0003_ms2"
down_revision: Union[str, None] = "0002_ms2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Copia fija del catálogo: una migración no debe importar los modelos (si el
# modelo cambia después, esta migración tiene que seguir creando lo mismo).
ESTADOS = [
    (1, "Recibido"),
    (2, "Esperando diagnóstico"),
    (3, "Esperando aprobación de presupuesto"),
    (4, "Esperando repuestos"),
    (5, "En reparación"),
    (6, "Listo"),
    (7, "Entregado"),
    (8, "Cancelado"),
]


def upgrade() -> None:
    # --- CATÁLOGO DE ESTADOS (§4.2) ---
    estado_orden = op.create_table("estado_orden",
    sa.Column("estado_codigo", sa.SmallInteger(), autoincrement=False, nullable=False),
    sa.Column("nombre", sa.String(length=60), nullable=False),
    sa.CheckConstraint("estado_codigo between 1 and 8", name=op.f("ck_estado_orden_codigo_valido")),
    sa.PrimaryKeyConstraint("estado_codigo", name=op.f("pk_estado_orden")),
    sa.UniqueConstraint("nombre", name=op.f("uq_estado_orden_nombre"))
    )
    # Carga del catálogo: toda base migrada queda con los 8 estados oficiales.
    op.bulk_insert(
        estado_orden,
        [{"estado_codigo": codigo, "nombre": nombre} for codigo, nombre in ESTADOS],
    )

    # --- INGRESO FÍSICO DEL VEHÍCULO (§4.1) ---
    # registrado_por_id: REF lógica a MS1, sin FK física (§8).
    op.create_table("ingreso_vehiculo",
    sa.Column("ingreso_id", sa.Integer(), nullable=False),
    sa.Column("vehiculo_id", sa.Integer(), nullable=False),
    sa.Column("fecha_hora", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("salida_en", sa.DateTime(timezone=True), nullable=True),
    sa.Column("registrado_por_id", sa.Integer(), nullable=False),
    sa.CheckConstraint("registrado_por_id > 0", name=op.f("ck_ingreso_vehiculo_registrado_por_positivo")),
    sa.CheckConstraint("salida_en is null or salida_en >= fecha_hora", name=op.f("ck_ingreso_vehiculo_salida_posterior")),
    sa.ForeignKeyConstraint(["vehiculo_id"], ["vehiculo.vehiculo_id"], name=op.f("fk_ingreso_vehiculo_vehiculo_id_vehiculo"), ondelete="RESTRICT"),
    sa.PrimaryKeyConstraint("ingreso_id", name=op.f("pk_ingreso_vehiculo"))
    )
    op.create_index(op.f("ix_ingreso_vehiculo_vehiculo_id"), "ingreso_vehiculo", ["vehiculo_id"], unique=False)
    # --- ORDEN DE TRABAJO ---
    # FK locales RESTRICT: las órdenes no se borran (cancelar es un estado).
    # Los *_id de usuarios son REF lógicas a MS1, sin FK física (§8).
    op.create_table("orden_trabajo",
    sa.Column("orden_id", sa.Integer(), nullable=False),
    sa.Column("vehiculo_id", sa.Integer(), nullable=False),
    sa.Column("ingreso_id", sa.Integer(), nullable=False),
    sa.Column("estado_codigo", sa.SmallInteger(), server_default="1", nullable=False),
    sa.Column("mecanico_actual_id", sa.Integer(), nullable=True),
    sa.Column("creado_por_id", sa.Integer(), nullable=False),
    sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("diagnostico_texto", sa.Text(), nullable=True),
    sa.Column("fecha_diagnostico", sa.DateTime(timezone=True), nullable=True),
    sa.Column("diagnostico_autor_id", sa.Integer(), nullable=True),
    sa.Column("entregado_en", sa.DateTime(timezone=True), nullable=True),
    sa.Column("entregado_por_id", sa.Integer(), nullable=True),
    sa.Column("devuelto_en", sa.DateTime(timezone=True), nullable=True),
    sa.Column("devuelto_por_id", sa.Integer(), nullable=True),
    sa.CheckConstraint("(devuelto_en is null) = (devuelto_por_id is null)", name=op.f("ck_orden_trabajo_devolucion_completa")),
    sa.CheckConstraint("(diagnostico_texto is null) = (fecha_diagnostico is null) and (fecha_diagnostico is null) = (diagnostico_autor_id is null)", name=op.f("ck_orden_trabajo_diagnostico_completo")),
    sa.CheckConstraint("(entregado_en is null) = (entregado_por_id is null)", name=op.f("ck_orden_trabajo_entrega_completa")),
    sa.CheckConstraint("creado_por_id > 0", name=op.f("ck_orden_trabajo_creado_por_positivo")),
    sa.CheckConstraint("mecanico_actual_id is null or mecanico_actual_id > 0", name=op.f("ck_orden_trabajo_mecanico_positivo")),
    sa.ForeignKeyConstraint(["estado_codigo"], ["estado_orden.estado_codigo"], name=op.f("fk_orden_trabajo_estado_codigo_estado_orden"), ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["ingreso_id"], ["ingreso_vehiculo.ingreso_id"], name=op.f("fk_orden_trabajo_ingreso_id_ingreso_vehiculo"), ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["vehiculo_id"], ["vehiculo.vehiculo_id"], name=op.f("fk_orden_trabajo_vehiculo_id_vehiculo"), ondelete="RESTRICT"),
    sa.PrimaryKeyConstraint("orden_id", name=op.f("pk_orden_trabajo"))
    )
    op.create_index(op.f("ix_orden_trabajo_estado_codigo"), "orden_trabajo", ["estado_codigo"], unique=False)
    op.create_index(op.f("ix_orden_trabajo_ingreso_id"), "orden_trabajo", ["ingreso_id"], unique=False)
    op.create_index(op.f("ix_orden_trabajo_mecanico_actual_id"), "orden_trabajo", ["mecanico_actual_id"], unique=False)
    op.create_index(op.f("ix_orden_trabajo_vehiculo_id"), "orden_trabajo", ["vehiculo_id"], unique=False)
    # --- HISTORIAL DE ESTADOS (trazabilidad, solo inserción) ---
    op.create_table("historial_estado",
    sa.Column("historial_id", sa.Integer(), nullable=False),
    sa.Column("orden_id", sa.Integer(), nullable=False),
    sa.Column("estado_anterior", sa.SmallInteger(), nullable=True),
    sa.Column("estado_nuevo", sa.SmallInteger(), nullable=False),
    sa.Column("actor_usuario_id", sa.Integer(), nullable=True),
    sa.Column("origen", sa.String(length=10), server_default="usuario", nullable=False),
    sa.Column("fecha_hora", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("observacion", sa.Text(), nullable=True),
    sa.CheckConstraint("origen in ('usuario', 'sistema')", name=op.f("ck_historial_estado_origen_valido")),
    sa.CheckConstraint("actor_usuario_id is null or actor_usuario_id > 0", name=op.f("ck_historial_estado_actor_positivo")),
    sa.CheckConstraint("estado_anterior is null or estado_anterior <> estado_nuevo", name=op.f("ck_historial_estado_cambio_real")),
    sa.ForeignKeyConstraint(["estado_anterior"], ["estado_orden.estado_codigo"], name=op.f("fk_historial_estado_estado_anterior_estado_orden"), ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["estado_nuevo"], ["estado_orden.estado_codigo"], name=op.f("fk_historial_estado_estado_nuevo_estado_orden"), ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["orden_id"], ["orden_trabajo.orden_id"], name=op.f("fk_historial_estado_orden_id_orden_trabajo"), ondelete="RESTRICT"),
    sa.PrimaryKeyConstraint("historial_id", name=op.f("pk_historial_estado"))
    )
    op.create_index("ix_historial_estado_orden_fecha", "historial_estado", ["orden_id", "fecha_hora"], unique=False)


def downgrade() -> None:
    # Orden inverso a upgrade (primero lo que depende de otras tablas).
    op.drop_index("ix_historial_estado_orden_fecha", table_name="historial_estado")
    op.drop_table("historial_estado")
    op.drop_index(op.f("ix_orden_trabajo_vehiculo_id"), table_name="orden_trabajo")
    op.drop_index(op.f("ix_orden_trabajo_mecanico_actual_id"), table_name="orden_trabajo")
    op.drop_index(op.f("ix_orden_trabajo_ingreso_id"), table_name="orden_trabajo")
    op.drop_index(op.f("ix_orden_trabajo_estado_codigo"), table_name="orden_trabajo")
    op.drop_table("orden_trabajo")
    op.drop_index(op.f("ix_ingreso_vehiculo_vehiculo_id"), table_name="ingreso_vehiculo")
    op.drop_table("ingreso_vehiculo")
    op.drop_table("estado_orden")
