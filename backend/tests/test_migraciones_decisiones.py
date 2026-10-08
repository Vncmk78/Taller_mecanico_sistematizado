"""DDL PostgreSQL de las migraciones aditivas de coordinación de decisiones."""
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from services.ms2_taller.models import Base as BaseMS2
from services.ms3_presupuestos.models import Base as BaseMS3


@pytest.mark.parametrize("servicio,archivo,base,columna,restriccion,head,anterior", [
    ("ms2_taller", "0006_decisiones_presupuesto_ms2.py", BaseMS2, "decision_presupuesto_id",
     "uq_historial_estado_decision_presupuesto_id", "0006_ms2", "0005_ms2"),
    ("ms3_presupuestos", "0004_stock_decision_ms3.py", BaseMS3, "repuestos_disponibles",
     "ck_decision_presupuesto_stock_solo_aprobacion", "0004_ms3", "0003_ms3"),
])
def test_migracion_agrega_referencia_o_snapshot_sin_reescribir_historia(
    servicio, archivo, base, columna, restriccion, head, anterior,
):
    script = ScriptDirectory.from_config(Config(f"services/{servicio}/alembic.ini"))
    assert script.get_heads() == [head]
    assert script.get_revision(head).down_revision == anterior
    ruta = Path(__file__).resolve().parents[1] / "services" / servicio / "alembic" / "versions" / archivo
    spec = spec_from_file_location(f"migracion_{head}", ruta)
    modulo = module_from_spec(spec)
    spec.loader.exec_module(modulo)

    def sql(operacion):
        buffer = StringIO()
        contexto = MigrationContext.configure(dialect_name="postgresql", opts={
            "as_sql": True, "output_buffer": buffer, "target_metadata": base.metadata,
        })
        with Operations.context(contexto):
            operacion()
        return buffer.getvalue()

    upgrade = sql(modulo.upgrade)
    assert f"ADD COLUMN {columna}" in upgrade
    assert restriccion in upgrade
    assert "NOT NULL" not in upgrade and "DEFAULT" not in upgrade
    assert "UPDATE " not in upgrade and "DELETE " not in upgrade
    assert "FOREIGN KEY" not in upgrade
    downgrade = sql(modulo.downgrade)
    assert f"DROP COLUMN {columna}" in downgrade
    assert f"DROP CONSTRAINT {restriccion}" in downgrade
