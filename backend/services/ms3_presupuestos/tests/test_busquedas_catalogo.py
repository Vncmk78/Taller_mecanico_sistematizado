"""Búsquedas de repuestos y proveedores: filtros e índices (migración 0006_ms3).

1. Filtros: texto sin mayúsculas ni tildes, comodines escapados, con/sin
   stock, orden por stock, proveedores con/sin repuestos.
2. Índices: con `enable_seqscan = off`, el EXPLAIN de la consulta REAL que
   arma el repositorio debe usar el índice esperado. Si alguien cambia la
   expresión del filtro y deja de coincidir con la del índice, esto falla.
3. La base impide proveedores repetidos cambiando mayúsculas.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import Proveedor, Repuesto
from services.ms3_presupuestos.persistencia.repositorios import (
    FiltroRepuestos,
    RepositorioProveedores,
    RepositorioRepuestos,
)
from services.ms3_presupuestos.tests import fabricas
from shared.auth import NombreRol, crear_token_acceso

MECANICO = {"Authorization": "Bearer " + crear_token_acceso(
    usuario_id=datos.MECANICO_ID, roles=[NombreRol.MECANICO],
    clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256")}


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def catalogo(db: Session) -> tuple[Proveedor, str]:
    """Un proveedor con repuestos de nombres con tildes y mayúsculas, y una marca única."""
    marca = uuid.uuid4().hex[:6]
    proveedor = fabricas.nuevo_proveedor(db, f"Distribuidora Ñuñoa {marca}",
                                         contacto="Óscar Pérez / ventas@ñuñoa.cl", repuestos=())
    for nombre, stock in [("Bujía Iridium", 8), ("BUJIA estándar", 0), ("Filtro de aceite", 3),
                          ("Correa 10% reforzada", 5), ("Correa 100 dientes", 1)]:
        fabricas.nuevo_repuesto(db, f"{nombre} {marca}", stock=stock, proveedor=proveedor)
    return proveedor, marca


def _nombres(respuesta) -> list[str]:
    assert respuesta.status_code == 200, respuesta.text
    return [r["nombre"].rsplit(" ", 1)[0] for r in respuesta.json()["repuestos"]]


# ================================================================== filtros ==

def test_busqueda_ignora_mayusculas_y_tildes(api: TestClient, catalogo) -> None:
    proveedor, _ = catalogo
    base = f"/repuestos?proveedor_id={proveedor.proveedor_id}"
    esperado = ["BUJIA estándar", "Bujía Iridium"]
    assert _nombres(api.get(f"{base}&q=bujia", headers=MECANICO)) == esperado
    assert _nombres(api.get(f"{base}&q=BUJÍA", headers=MECANICO)) == esperado
    assert _nombres(api.get(f"{base}&q=estandar", headers=MECANICO)) == ["BUJIA estándar"]


def test_los_comodines_del_usuario_se_buscan_literalmente(api: TestClient, catalogo) -> None:
    proveedor, _ = catalogo
    base = f"/repuestos?proveedor_id={proveedor.proveedor_id}"
    # Sin escapar, "10%" también encontraría "Correa 100 dientes".
    assert _nombres(api.get(f"{base}&q=10%25", headers=MECANICO)) == ["Correa 10% reforzada"]
    assert _nombres(api.get(f"{base}&q=_", headers=MECANICO)) == []


def test_filtro_con_y_sin_stock(api: TestClient, catalogo) -> None:
    proveedor, _ = catalogo
    base = f"/repuestos?proveedor_id={proveedor.proveedor_id}"
    assert _nombres(api.get(f"{base}&con_stock=false", headers=MECANICO)) == ["BUJIA estándar"]
    con_stock = api.get(f"{base}&con_stock=true", headers=MECANICO)
    assert con_stock.json()["total"] == 4


def test_ordenar_por_stock(api: TestClient, catalogo) -> None:
    proveedor, _ = catalogo
    base = f"/repuestos?proveedor_id={proveedor.proveedor_id}"
    asc = api.get(f"{base}&ordenar=stock_asc", headers=MECANICO).json()["repuestos"]
    assert [r["stock"] for r in asc] == [0, 1, 3, 5, 8]
    desc = api.get(f"{base}&ordenar=stock_desc&limite=2", headers=MECANICO).json()
    assert [r["stock"] for r in desc["repuestos"]] == [8, 5] and desc["total"] == 5
    assert api.get(f"{base}&ordenar=precio", headers=MECANICO).status_code == 422


def test_filtros_combinados(api: TestClient, catalogo) -> None:
    proveedor, _ = catalogo
    r = api.get(f"/repuestos?proveedor_id={proveedor.proveedor_id}&q=correa&con_stock=true"
                "&ordenar=stock_asc", headers=MECANICO)
    assert _nombres(r) == ["Correa 100 dientes", "Correa 10% reforzada"]


def test_proveedor_por_contacto_con_tildes(api: TestClient, catalogo) -> None:
    proveedor, marca = catalogo
    r = api.get("/proveedores?q=oscar perez", headers=MECANICO).json()
    assert proveedor.proveedor_id in [p["proveedor_id"] for p in r["proveedores"]]
    r = api.get(f"/proveedores?q=nunoa {marca}", headers=MECANICO).json()
    assert [p["proveedor_id"] for p in r["proveedores"]] == [proveedor.proveedor_id]


def test_proveedores_con_y_sin_repuestos(api: TestClient, db: Session, catalogo) -> None:
    proveedor, marca = catalogo
    vacio = fabricas.nuevo_proveedor(db, f"Sin stock {marca}", repuestos=())
    con = api.get(f"/proveedores?q={marca}&con_repuestos=true", headers=MECANICO).json()
    sin = api.get(f"/proveedores?q={marca}&con_repuestos=false", headers=MECANICO).json()
    assert [p["proveedor_id"] for p in con["proveedores"]] == [proveedor.proveedor_id]
    assert [p["proveedor_id"] for p in sin["proveedores"]] == [vacio.proveedor_id]


def test_texto_vacio_no_filtra(api: TestClient, catalogo) -> None:
    proveedor, _ = catalogo
    r = api.get(f"/repuestos?proveedor_id={proveedor.proveedor_id}&q=%20%20", headers=MECANICO)
    assert r.json()["total"] == 5


# ========================================================= uso de índices ==

def _plan(db: Session, consulta: Select) -> str:
    """EXPLAIN de la consulta tal cual la ejecuta SQLAlchemy (mismos parámetros)."""
    with db.begin_nested():
        db.execute(text("SET LOCAL enable_seqscan = off"))
        conexion = db.connection()
        compilada = consulta.compile(dialect=conexion.dialect)
        filas = conexion.exec_driver_sql(f"EXPLAIN {compilada}", compilada.params).scalars().all()
    return "\n".join(filas)


@pytest.mark.parametrize(("descripcion", "consulta", "indice"), [
    ("repuesto por texto",
     lambda: RepositorioRepuestos._filtro(FiltroRepuestos(texto="bujia")),
     "ix_repuesto_nombre_trgm"),
    ("proveedor por texto (nombre)",
     lambda: RepositorioProveedores._filtro(None, "ñuñoa", None),
     "ix_proveedor_nombre_trgm"),
    ("proveedor por texto (contacto)",
     lambda: RepositorioProveedores._filtro(None, "ñuñoa", None),
     "ix_proveedor_contacto_trgm"),
    ("repuestos de un proveedor",
     lambda: RepositorioRepuestos._filtro(FiltroRepuestos(proveedor_id=1)),
     "proveedor"),
])
def test_la_consulta_real_puede_usar_su_indice(db: Session, descripcion, consulta, indice) -> None:
    plan = _plan(db, consulta())
    assert indice in plan, f"{descripcion}: no usa {indice}\n{plan}"


def test_listado_ordenado_usa_el_indice_de_orden(db: Session) -> None:
    repo = RepositorioRepuestos(db)
    consulta = repo._filtro(FiltroRepuestos()).order_by(
        text("lower(repuesto.nombre)"), Repuesto.repuesto_id).limit(20)
    assert "ix_repuesto_nombre_orden" in _plan(db, consulta)


def test_existen_los_indices_de_la_migracion(db: Session) -> None:
    nombres = set(db.execute(text(
        "select indexname from pg_indexes where tablename in ('repuesto', 'proveedor')")).scalars())
    assert {"ix_repuesto_nombre_trgm", "ix_proveedor_nombre_trgm", "ix_proveedor_contacto_trgm",
            "ix_repuesto_nombre_orden", "ix_proveedor_nombre_orden", "uq_proveedor_nombre_ci",
            "uq_repuesto_proveedor_nombre", "ix_repuesto_proveedor_id"} <= nombres


# ================================================= integridad del nombre ==

def test_la_base_impide_proveedores_repetidos_por_mayusculas(db: Session) -> None:
    nombre = f"Acme {uuid.uuid4().hex[:6]}"
    db.add(Proveedor(nombre=nombre, contacto="x"))
    db.flush()
    with pytest.raises(IntegrityError, match="uq_proveedor_nombre_ci"), db.begin_nested():
        db.add(Proveedor(nombre=nombre.upper(), contacto="y"))
        db.flush()
