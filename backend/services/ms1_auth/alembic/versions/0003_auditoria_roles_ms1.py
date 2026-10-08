"""Auditoría de cambios de roles (Semana 4) — MS1

Revision ID: 0003_auditoria_roles_ms1
Revises: 0002_roles_ms1
Create Date: 2026-10-08

Crea historial_rol: cada alta o baja de un rol de un usuario guarda qué rol
cambió, la acción ('asignado' / 'retirado'), el usuario responsable (vacío
cuando lo hace el sistema) y la fecha/hora. `usuario_rol` conserva solo el
estado vigente; la historia de las bajas —que borran su fila— vive aquí.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0003_auditoria_roles_ms1"
down_revision: Union[str, None] = "0002_roles_ms1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historial_rol",
        sa.Column("historial_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("rol_id", sa.Integer(), nullable=False),
        sa.Column("accion", sa.String(length=10), nullable=False),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column(
            "fecha_hora",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "accion in ('asignado', 'retirado')",
            name=op.f("ck_historial_rol_accion_valida"),
        ),
        sa.CheckConstraint(
            "responsable_id is null or responsable_id > 0",
            name=op.f("ck_historial_rol_responsable_positivo"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.usuario_id"],
            name=op.f("fk_historial_rol_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rol_id"], ["rol.rol_id"],
            name=op.f("fk_historial_rol_rol_id_rol"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["responsable_id"], ["usuario.usuario_id"],
            name=op.f("fk_historial_rol_responsable_id_usuario"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("historial_id", name=op.f("pk_historial_rol")),
    )
    op.create_index(
        "ix_historial_rol_usuario_fecha",
        "historial_rol",
        ["usuario_id", "fecha_hora"],
    )


def downgrade() -> None:
    op.drop_index("ix_historial_rol_usuario_fecha", table_name="historial_rol")
    op.drop_table("historial_rol")
