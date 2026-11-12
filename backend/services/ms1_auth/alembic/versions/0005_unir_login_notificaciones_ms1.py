"""Une las revisiones de protección de login y notificaciones de MS1.

Revision ID: 0005_integracion_ms1
Revises: 0004_intentos_login_ms1, 0004_notificaciones_ms1

Ambas revisiones agregan objetos independientes. Esta unión conserva sus IDs
y hace que una base en cualquiera de ellas aplique la otra antes del nuevo head.
"""

revision = "0005_integracion_ms1"
down_revision = ("0004_intentos_login_ms1", "0004_notificaciones_ms1")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
