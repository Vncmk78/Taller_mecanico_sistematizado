"""Tratamiento de intentos repetidos de autenticación incorrecta (MS1)

Revision ID: 0004_intentos_login_ms1
Revises: 0003_auditoria_roles_ms1
Create Date: 2026-10-18

Agrega al modelo Usuario dos campos para registrar el número de fallos
consecutivos de login (`intentos_fallidos`) y, si supera el umbral, la
fecha/hora hasta la que la cuenta queda bloqueada (`bloqueado_hasta`).

El ingreso correcto de las credenciales reinicia ambos valores.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# identificadores de la revisión, usados por Alembic.
revision: str = "0004_intentos_login_ms1"
down_revision: Union[str, None] = "0003_auditoria_roles_ms1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column(
            "intentos_fallidos",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "usuario",
        sa.Column("bloqueado_hasta", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("usuario", "bloqueado_hasta")
    op.drop_column("usuario", "intentos_fallidos")
