"""Versión aprobada bloqueada: toda modificación es una nueva versión — MS3.

Revision ID: 0009_ms3
Revises: 0008_ms3

Semana 8 · "Implementar bloqueo de la versión aprobada y creación obligatoria
de una nueva versión al modificarla".

0003_ms3 ya impide tocar una versión aprobada (fila e ítems). Este trigger
cierra lo que faltaba al CREAR una versión, para que la base lo garantice
aunque el código se equivoque:

1. Si el presupuesto ya tiene una versión aprobada, la nueva versión DEBE
   registrarse como modificación (es_modificacion = true); si no la tiene, NO
   puede ser modificación.
2. No se crea una versión mientras haya otra en borrador: los cambios van en
   ese borrador (un solo borrador abierto).

No toca datos existentes.
"""
from alembic import op

revision = "0009_ms3"
down_revision = "0008_ms3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE FUNCTION fn_version_nueva_es_modificacion() RETURNS trigger AS $$
DECLARE
    hay_aprobada boolean;
BEGIN
    IF EXISTS (SELECT 1 FROM version_presupuesto
               WHERE presupuesto_id = NEW.presupuesto_id AND enviado_en IS NULL) THEN
        RAISE EXCEPTION 'El presupuesto % ya tiene una versión en borrador; los cambios van en ese borrador',
            NEW.presupuesto_id USING ERRCODE = 'check_violation';
    END IF;

    SELECT EXISTS (SELECT 1 FROM version_presupuesto
                   WHERE presupuesto_id = NEW.presupuesto_id AND bloqueada_en IS NOT NULL)
      INTO hay_aprobada;
    IF NEW.es_modificacion IS DISTINCT FROM hay_aprobada THEN
        IF hay_aprobada THEN
            RAISE EXCEPTION 'El presupuesto % tiene una versión aprobada: la nueva versión debe registrarse como modificación',
                NEW.presupuesto_id USING ERRCODE = 'check_violation';
        END IF;
        RAISE EXCEPTION 'El presupuesto % no tiene una versión aprobada: la nueva versión no es una modificación',
            NEW.presupuesto_id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_version_nueva_es_modificacion
    BEFORE INSERT ON version_presupuesto
    FOR EACH ROW EXECUTE FUNCTION fn_version_nueva_es_modificacion();
""")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_version_nueva_es_modificacion ON version_presupuesto")
    op.execute("DROP FUNCTION IF EXISTS fn_version_nueva_es_modificacion()")
