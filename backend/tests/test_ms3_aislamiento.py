"""Aislamiento de la base de datos de MS3 respecto de MS1, MS2 y MS4 (§8).

Pruebas sin base de datos: revisan el modelo ORM, la configuración, las
migraciones y los imports del código de MS3.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table

from services.ms1_auth import models as _modelos_ms1  # noqa: F401
from services.ms1_auth.config import settings as settings_ms1
from services.ms1_auth.db import Base as BaseMS1
from services.ms2_taller import models as _modelos_ms2  # noqa: F401
from services.ms2_taller.config import settings as settings_ms2
from services.ms2_taller.db import Base as BaseMS2
from services.ms3_presupuestos import aislamiento
from services.ms3_presupuestos import models as _modelos_ms3  # noqa: F401
from services.ms3_presupuestos.config import Settings as SettingsMS3
from services.ms3_presupuestos.db import Base as BaseMS3
from services.ms3_presupuestos.db import engine as engine_ms3
from services.ms4_evidencias import models as _modelos_ms4  # noqa: F401
from services.ms4_evidencias.config import settings as settings_ms4
from services.ms4_evidencias.db import Base as BaseMS4

RAIZ_MS3 = Path(__file__).resolve().parents[1] / "services" / "ms3_presupuestos"
AJENAS = {"MS1": BaseMS1.metadata, "MS2": BaseMS2.metadata, "MS4": BaseMS4.metadata}


# ------------------------------------------------------------------ modelo --

def test_modelo_de_ms3_esta_aislado() -> None:
    assert aislamiento.problemas_de_metadata(BaseMS3.metadata, AJENAS) == []


def test_ms3_tiene_su_propio_metadata() -> None:
    for metadata in AJENAS.values():
        assert metadata is not BaseMS3.metadata


def test_todas_las_fk_de_ms3_quedan_dentro_de_ms3() -> None:
    tablas = set(BaseMS3.metadata.tables)
    for tabla in BaseMS3.metadata.tables.values():
        for fk in tabla.foreign_keys:
            assert fk.column.table.name in tablas, fk.target_fullname


@pytest.mark.parametrize(
    ("tabla", "columna"),
    [(t, c) for t, cols in aislamiento.REFERENCIAS_LOGICAS.items() for c in cols],
)
def test_referencias_a_otros_servicios_son_logicas(tabla: str, columna: str) -> None:
    col = BaseMS3.metadata.tables[tabla].c[columna]
    assert not col.foreign_keys
    assert isinstance(col.type, Integer)


def test_detecta_una_fk_hacia_otro_servicio() -> None:
    """La verificación no es decorativa: una FK a MS2 se reporta."""
    md = MetaData()
    ajena = MetaData()
    orden = Table("orden_trabajo", ajena, Column("orden_id", Integer, primary_key=True))
    Table("presupuesto", md, Column("presupuesto_id", Integer, primary_key=True),
          Column("orden_id", Integer, ForeignKey(orden.c.orden_id)))
    problemas = aislamiento.problemas_de_metadata(md, {"MS2": ajena})
    assert any("apunta fuera de MS3" in p for p in problemas)
    assert any("no puede tener FK" in p for p in problemas)


def test_detecta_tablas_compartidas() -> None:
    md = MetaData()
    Table("usuario", md, Column("usuario_id", Integer, primary_key=True))
    problemas = aislamiento.problemas_de_metadata(md, {"MS1": BaseMS1.metadata})
    assert any("tablas compartidas con MS1" in p for p in problemas)


# ------------------------------------------------------------ configuración --

def test_url_de_ms3_se_lee_con_su_prefijo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MS3_DATABASE_URL", "postgresql+psycopg://u:p@h:5435/solo_ms3")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:5432/otra")
    monkeypatch.setenv("MS2_DATABASE_URL", "postgresql+psycopg://u:p@h:5434/taller_ms2")
    assert SettingsMS3().DATABASE_URL.endswith("/solo_ms3")


def test_url_por_defecto_de_ms3_es_su_propia_base() -> None:
    campo = SettingsMS3.model_fields["DATABASE_URL"].default
    assert campo.endswith("/taller_ms3")


def test_engine_de_ms3_no_apunta_a_la_base_de_otro_servicio() -> None:
    ajenas = {"MS1": settings_ms1.DATABASE_URL, "MS2": settings_ms2.DATABASE_URL,
              "MS4": settings_ms4.DATABASE_URL}
    assert aislamiento.problemas_de_urls(str(engine_ms3.url), ajenas) == []


def test_urls_misma_base_se_reportan_y_mismo_servidor_no() -> None:
    neon = "postgresql+psycopg://u:p@ep-x.neon.tech/{}"
    assert aislamiento.problemas_de_urls(neon.format("taller_ms3"),
                                         {"MS2": neon.format("taller_ms2")}) == []
    problemas = aislamiento.problemas_de_urls(neon.format("taller_ms2"),
                                              {"MS2": neon.format("taller_ms2")})
    assert problemas and "MS2" in problemas[0]


# --------------------------------------------------------------- migraciones --

def _fuentes_migraciones() -> list[Path]:
    return sorted((RAIZ_MS3 / "alembic" / "versions").glob("*.py"))


def test_migraciones_solo_crean_fk_hacia_tablas_de_ms3() -> None:
    tablas = set(BaseMS3.metadata.tables)
    patron = re.compile(r"""(?:ForeignKey\(\s*["']|REFERENCES\s+)(\w+)""", re.IGNORECASE)
    for archivo in _fuentes_migraciones():
        for destino in patron.findall(archivo.read_text(encoding="utf-8")):
            assert destino in tablas, f"{archivo.name}: FK hacia {destino}"


def test_migraciones_solo_crean_tablas_de_ms3() -> None:
    tablas = set(BaseMS3.metadata.tables)
    patron = re.compile(r"""create_table\(\s*["'](\w+)""")
    creadas = {t for a in _fuentes_migraciones()
               for t in patron.findall(a.read_text(encoding="utf-8"))}
    assert creadas == tablas


def test_alembic_de_ms3_usa_solo_sus_migraciones() -> None:
    ini = (RAIZ_MS3 / "alembic.ini").read_text(encoding="utf-8")
    assert re.search(r"script_location\s*=.*ms3_presupuestos", ini)
    env = (RAIZ_MS3 / "alembic" / "env.py").read_text(encoding="utf-8")
    assert "from services.ms3_presupuestos.db import Base, engine" in env
    assert not re.search(r"ms[124]_", env)


# --------------------------------------------------------------------- código --

def _imports(archivo: Path) -> set[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos |= {n.name for n in nodo.names}
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.add(nodo.module)
    return modulos


def test_codigo_de_ms3_no_importa_otros_microservicios() -> None:
    prohibidos = ("services.ms1_", "services.ms2_", "services.ms4_")
    for archivo in RAIZ_MS3.rglob("*.py"):
        for modulo in _imports(archivo):
            assert not modulo.startswith(prohibidos), (
                f"{archivo.relative_to(RAIZ_MS3)} importa {modulo}"
            )
