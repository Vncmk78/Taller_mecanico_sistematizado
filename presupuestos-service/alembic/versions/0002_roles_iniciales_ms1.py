"""Roles iniciales de MS1.

Revision ID: 0002_roles_ms1
Revises: 0001_ms1
Create Date: 2026-09-17
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_roles_ms1"
down_revision: Union[str, None] = "0001_ms1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOMBRES_ROL = ("cliente", "mecanico", "administrador")


def upgrade() -> None:
    tabla_rol = sa.table("rol", sa.column("nombre", sa.String(length=40)))
    op.bulk_insert(tabla_rol, [{"nombre": nombre} for nombre in _NOMBRES_ROL])


def downgrade() -> None:
    conexion = op.get_bind()
    tabla_rol = sa.table(
        "rol",
        sa.column("rol_id", sa.Integer()),
        sa.column("nombre", sa.String(length=40)),
    )
    tabla_usuario_rol = sa.table(
        "usuario_rol",
        sa.column("rol_id", sa.Integer()),
    )
    ids_roles = sa.select(tabla_rol.c.rol_id).where(
        tabla_rol.c.nombre.in_(_NOMBRES_ROL)
    )
    conexion.execute(sa.delete(tabla_usuario_rol).where(tabla_usuario_rol.c.rol_id.in_(ids_roles)))
    conexion.execute(sa.delete(tabla_rol).where(tabla_rol.c.nombre.in_(_NOMBRES_ROL)))
