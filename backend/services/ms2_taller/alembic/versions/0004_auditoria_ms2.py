"""Campos de auditoría de estados y responsables (Semana 3) — MS2

Revision ID: 0004_ms2
Revises: 0003_ms2
Create Date: 2026-09-23

Completa la auditoría de la orden de trabajo (quién, cuándo, qué y por qué):

- historial_asignacion (nueva): auditoría de RESPONSABLES. Cada asignación o
  reasignación de mecánico guarda mecánico anterior/nuevo, administrador que la
  hizo, fecha/hora y observación.
- historial_estado: el actor queda obligatorio cuando el cambio lo hace un
  usuario y vacío cuando lo hace el sistema; la observación no puede venir vacía.
- orden_trabajo: columna actualizado_en (última modificación) y CHECK de que
  los hitos (diagnóstico, entrega, devolución) no sean anteriores a creado_en.

Las REF a usuarios de MS1 son columnas sin FK (§8).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0004_ms2"
down_revision: Union[str, None] = "0003_ms2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- HISTORIAL DE ASIGNACIÓN (auditoría de responsables) ---
    op.create_table(
        "historial_asignacion",
        sa.Column("asignacion_id", sa.Integer(), nullable=False),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("mecanico_anterior_id", sa.Integer(), nullable=True),
        sa.Column("mecanico_nuevo_id", sa.Integer(), nullable=False),
        sa.Column("administrador_id", sa.Integer(), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "mecanico_nuevo_id > 0 and administrador_id > 0 "
            "and (mecanico_anterior_id is null or mecanico_anterior_id > 0)",
            name=op.f("ck_historial_asignacion_ids_positivos"),
        ),
        sa.CheckConstraint(
            "mecanico_anterior_id is null or mecanico_anterior_id <> mecanico_nuevo_id",
            name=op.f("ck_historial_asignacion_cambio_real"),
        ),
        sa.CheckConstraint(
            "observacion is null or btrim(observacion) <> ''",
            name=op.f("ck_historial_asignacion_observacion_no_vacia"),
        ),
        sa.ForeignKeyConstraint(
            ["orden_id"], ["orden_trabajo.orden_id"],
            name=op.f("fk_historial_asignacion_orden_id_orden_trabajo"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("asignacion_id", name=op.f("pk_historial_asignacion")),
    )
    op.create_index(
        "ix_historial_asignacion_orden_fecha",
        "historial_asignacion",
        ["orden_id", "fecha_hora"],
    )

    # --- HISTORIAL DE ESTADO: coherencia origen ↔ actor y observación ---
    # El nombre va sin prefijo: la convención de nombres antepone ck_<tabla>_.
    op.create_check_constraint(
        "actor_segun_origen",
        "historial_estado",
        "(origen = 'usuario' and actor_usuario_id is not null) "
        "or (origen = 'sistema' and actor_usuario_id is null)",
    )
    op.create_check_constraint(
        "observacion_no_vacia",
        "historial_estado",
        "observacion is null or btrim(observacion) <> ''",
    )

    # --- ORDEN DE TRABAJO: última modificación y fechas coherentes ---
    op.add_column(
        "orden_trabajo",
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "fechas_coherentes",
        "orden_trabajo",
        "(fecha_diagnostico is null or fecha_diagnostico >= creado_en) "
        "and (entregado_en is null or entregado_en >= creado_en) "
        "and (devuelto_en is null or devuelto_en >= creado_en)",
    )


def downgrade() -> None:
    # Se dropean por el nombre final ya prefijado por la convención (op.f evita
    # que se vuelva a anteponer el prefijo).
    op.drop_constraint(op.f("ck_orden_trabajo_fechas_coherentes"), "orden_trabajo", type_="check")
    op.drop_column("orden_trabajo", "actualizado_en")
    op.drop_constraint(op.f("ck_historial_estado_observacion_no_vacia"), "historial_estado", type_="check")
    op.drop_constraint(op.f("ck_historial_estado_actor_segun_origen"), "historial_estado", type_="check")
    op.drop_index("ix_historial_asignacion_orden_fecha", table_name="historial_asignacion")
    op.drop_table("historial_asignacion")
