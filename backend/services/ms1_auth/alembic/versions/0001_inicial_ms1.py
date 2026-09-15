"""Inicial MS1: usuario, rol, usuario_rol

Revision ID: 0001_ms1
Revises:
Create Date: 2026-09-10

Crea las tablas iniciales del microservicio de Autenticación y Usuarios según el
MER (recuadro "BD MS1"): Usuario, Rol y la tabla puente UsuarioRol que da soporte
a roles múltiples por usuario (§1.1).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0001_ms1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- USUARIO ---
    op.create_table(
        "usuario",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("correo", sa.String(length=255), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("contrasena_hash", sa.String(length=255), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("usuario_id", name="pk_usuario"),
        sa.UniqueConstraint("correo", name="uq_usuario_correo"),
    )

    # --- ROL ---
    op.create_table(
        "rol",
        sa.Column("rol_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("rol_id", name="pk_rol"),
        sa.UniqueConstraint("nombre", name="uq_rol_nombre"),
    )

    # --- USUARIO_ROL (tabla puente N:M, PK compuesta) ---
    op.create_table(
        "usuario_rol",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("rol_id", sa.Integer(), nullable=False),
        sa.Column(
            "asignado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("asignado_por_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("usuario_id", "rol_id", name="pk_usuario_rol"),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.usuario_id"],
            name="fk_usuario_rol_usuario_id_usuario",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rol_id"], ["rol.rol_id"],
            name="fk_usuario_rol_rol_id_rol",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asignado_por_id"], ["usuario.usuario_id"],
            name="fk_usuario_rol_asignado_por_id_usuario",
            ondelete="SET NULL",
        ),
    )


def downgrade() -> None:
    op.drop_table("usuario_rol")
    op.drop_table("rol")
    op.drop_table("usuario")
