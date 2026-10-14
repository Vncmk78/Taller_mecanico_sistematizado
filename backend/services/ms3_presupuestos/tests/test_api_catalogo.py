"""Endpoints de proveedores y repuestos contra PostgreSQL (persistencia ORM real).

Cada prueba usa la sesión de prueba (transacción revertida al final) y nombres
únicos, así no choca con la semilla si la base ya la tiene.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import (
    HistorialUmbral,
    MovimientoInventario,
    Proveedor,
    Repuesto,
)
from services.ms3_presupuestos.tests import fabricas
from shared.auth import NombreRol, crear_token_acceso


def _cabecera(rol: NombreRol, usuario_id: int) -> dict[str, str]:
    token = crear_token_acceso(
        usuario_id=usuario_id, roles=[rol],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


ADMIN = _cabecera(NombreRol.ADMINISTRADOR, datos.ADMIN_ID)
MECANICO = _cabecera(NombreRol.MECANICO, datos.MECANICO_ID)
CLIENTE = _cabecera(NombreRol.CLIENTE, datos.CLIENTE_ID)


def _nombre(base: str) -> str:
    return f"{base} {uuid.uuid4().hex[:6]}"


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def proveedor(api: TestClient) -> dict:
    r = api.post("/proveedores", headers=ADMIN,
                 json={"nombre": _nombre("Frenos Prueba"), "contacto": "ventas@frenos.cl"})
    assert r.status_code == 201, r.text
    return r.json()


def _crear_repuesto(api: TestClient, proveedor_id: int, **datos_extra) -> dict:
    cuerpo = {"proveedor_id": proveedor_id, "nombre": _nombre("Disco"), **datos_extra}
    r = api.post("/repuestos", headers=ADMIN, json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


# =============================================================== PROVEEDORES ==

def test_crear_proveedor_y_consultarlo(api: TestClient, db: Session, proveedor: dict) -> None:
    assert proveedor["cantidad_repuestos"] == 0 and proveedor["proveedor_id"] > 0
    guardado = db.get(Proveedor, proveedor["proveedor_id"])
    assert guardado.nombre == proveedor["nombre"] and guardado.contacto == "ventas@frenos.cl"
    r = api.get(f"/proveedores/{proveedor['proveedor_id']}", headers=MECANICO)
    assert r.status_code == 200 and r.json()["repuestos"] == []


def test_nombre_de_proveedor_repetido_sin_importar_mayusculas_es_409(
    api: TestClient, proveedor: dict
) -> None:
    r = api.post("/proveedores", headers=ADMIN,
                 json={"nombre": f"  {proveedor['nombre'].upper()} ", "contacto": "x"})
    assert r.status_code == 409 and "Ya existe" in r.json()["detail"]


def test_buscar_proveedores_por_texto_y_paginar(api: TestClient) -> None:
    marca = uuid.uuid4().hex[:8]
    for i in range(3):
        api.post("/proveedores", headers=ADMIN,
                 json={"nombre": f"Prov {marca} {i}", "contacto": f"c{i}@x.cl"})
    pagina = api.get(f"/proveedores?q={marca.upper()}&limite=2", headers=MECANICO).json()
    assert pagina["total"] == 3 and len(pagina["proveedores"]) == 2
    assert [p["nombre"] for p in pagina["proveedores"]] == [f"Prov {marca} 0", f"Prov {marca} 1"]
    siguiente = api.get(f"/proveedores?q={marca}&desde=2&limite=2", headers=MECANICO).json()
    assert [p["nombre"] for p in siguiente["proveedores"]] == [f"Prov {marca} 2"]


def test_modificar_proveedor(api: TestClient, proveedor: dict) -> None:
    pid = proveedor["proveedor_id"]
    r = api.patch(f"/proveedores/{pid}", headers=ADMIN, json={"contacto": "+56 9 1111 2222"})
    assert r.status_code == 200 and r.json()["contacto"] == "+56 9 1111 2222"
    assert r.json()["nombre"] == proveedor["nombre"]
    # Cambiar solo mayúsculas de su propio nombre no choca consigo mismo.
    r = api.patch(f"/proveedores/{pid}", headers=ADMIN, json={"nombre": proveedor["nombre"].upper()})
    assert r.status_code == 200
    assert api.patch(f"/proveedores/{pid}", headers=ADMIN, json={}).status_code == 422


def test_renombrar_a_un_nombre_ocupado_es_409(api: TestClient, proveedor: dict) -> None:
    otro = api.post("/proveedores", headers=ADMIN,
                    json={"nombre": _nombre("Otro"), "contacto": "x"}).json()
    r = api.patch(f"/proveedores/{otro['proveedor_id']}", headers=ADMIN,
                  json={"nombre": proveedor["nombre"]})
    assert r.status_code == 409


def test_eliminar_proveedor_sin_repuestos(api: TestClient, db: Session, proveedor: dict) -> None:
    pid = proveedor["proveedor_id"]
    assert api.delete(f"/proveedores/{pid}", headers=ADMIN).status_code == 204
    assert db.get(Proveedor, pid) is None
    assert api.get(f"/proveedores/{pid}", headers=ADMIN).status_code == 404


def test_no_se_elimina_un_proveedor_con_repuestos(api: TestClient, db: Session, proveedor: dict) -> None:
    _crear_repuesto(api, proveedor["proveedor_id"])
    db.commit()
    r = api.delete(f"/proveedores/{proveedor['proveedor_id']}", headers=ADMIN)
    assert r.status_code == 409 and "reasígnelos" in r.json()["detail"]
    assert db.get(Proveedor, proveedor["proveedor_id"]) is not None


# ================================================================= REPUESTOS ==

def test_alta_de_repuesto_con_stock_inicial_deja_un_ingreso(
    api: TestClient, db: Session, proveedor: dict
) -> None:
    rep = _crear_repuesto(api, proveedor["proveedor_id"], stock_inicial=12, umbral_particular=4)
    assert rep["stock"] == 12 and rep["umbral_efectivo"] == 4 and rep["bajo_umbral"] is False
    assert rep["proveedor_nombre"] == proveedor["nombre"]

    movimientos = db.scalars(select(MovimientoInventario)
                             .where(MovimientoInventario.repuesto_id == rep["repuesto_id"])).all()
    assert [(m.tipo, m.cantidad, m.registrado_por_id) for m in movimientos] == \
           [("ingreso", 12, datos.ADMIN_ID)]
    historial = db.scalars(select(HistorialUmbral)
                           .where(HistorialUmbral.repuesto_id == rep["repuesto_id"])).all()
    assert [(h.valor_anterior, h.valor_nuevo) for h in historial] == [(None, 4)]


def test_alta_sin_stock_no_inventa_movimientos(api: TestClient, db: Session, proveedor: dict) -> None:
    rep = _crear_repuesto(api, proveedor["proveedor_id"])
    assert rep["stock"] == 0
    assert db.scalars(select(MovimientoInventario)
                      .where(MovimientoInventario.repuesto_id == rep["repuesto_id"])).all() == []


def test_mismo_nombre_en_el_mismo_proveedor_es_409_y_en_otro_se_permite(
    api: TestClient, proveedor: dict
) -> None:
    rep = _crear_repuesto(api, proveedor["proveedor_id"])
    r = api.post("/repuestos", headers=ADMIN,
                 json={"proveedor_id": proveedor["proveedor_id"], "nombre": rep["nombre"].lower()})
    assert r.status_code == 409 and "ya tiene el repuesto" in r.json()["detail"]

    otro = api.post("/proveedores", headers=ADMIN,
                    json={"nombre": _nombre("Otro"), "contacto": "x"}).json()
    r = api.post("/repuestos", headers=ADMIN,
                 json={"proveedor_id": otro["proveedor_id"], "nombre": rep["nombre"]})
    assert r.status_code == 201


def test_la_base_tambien_impide_el_nombre_repetido(db: Session) -> None:
    proveedor = fabricas.nuevo_proveedor(db, repuestos=())
    db.add(Repuesto(proveedor=proveedor, nombre="Bujía", stock=1))
    db.flush()
    with pytest.raises(IntegrityError, match="uq_repuesto_proveedor_nombre"), db.begin_nested():
        db.add(Repuesto(proveedor=proveedor, nombre="BUJÍA", stock=1))
        db.flush()


def test_repuesto_con_proveedor_inexistente_es_404(api: TestClient) -> None:
    r = api.post("/repuestos", headers=ADMIN, json={"proveedor_id": 987654321, "nombre": "X"})
    assert r.status_code == 404


@pytest.mark.parametrize("cuerpo", [
    {"nombre": ""}, {"stock_inicial": -1}, {"umbral_particular": -1}, {"stock": 5},
])
def test_datos_invalidos_de_repuesto_son_422(api: TestClient, proveedor: dict, cuerpo: dict) -> None:
    base = {"proveedor_id": proveedor["proveedor_id"], "nombre": "Válido"}
    assert api.post("/repuestos", headers=ADMIN, json={**base, **cuerpo}).status_code == 422


def test_cambiar_umbral_queda_en_el_historial(api: TestClient, db: Session, proveedor: dict) -> None:
    rep = _crear_repuesto(api, proveedor["proveedor_id"], stock_inicial=3)
    rid = rep["repuesto_id"]
    r = api.patch(f"/repuestos/{rid}", headers=ADMIN,
                  json={"umbral_particular": 5, "observacion": "Rotación alta"})
    assert r.status_code == 200 and r.json()["bajo_umbral"] is True   # 3 < 5
    r = api.patch(f"/repuestos/{rid}", headers=ADMIN, json={"umbral_particular": None})
    assert r.status_code == 200 and r.json()["umbral_particular"] is None
    # Repetir el mismo valor no crea una fila (no hubo cambio).
    api.patch(f"/repuestos/{rid}", headers=ADMIN, json={"umbral_particular": None})

    historial = db.scalars(select(HistorialUmbral).where(HistorialUmbral.repuesto_id == rid)
                           .order_by(HistorialUmbral.historial_id)).all()
    assert [(h.valor_anterior, h.valor_nuevo, h.administrador_id, h.observacion) for h in historial] == [
        (None, 5, datos.ADMIN_ID, "Rotación alta"), (5, None, datos.ADMIN_ID, None)]


def test_el_stock_no_se_edita_por_patch(api: TestClient, proveedor: dict) -> None:
    rep = _crear_repuesto(api, proveedor["proveedor_id"], stock_inicial=3)
    r = api.patch(f"/repuestos/{rep['repuesto_id']}", headers=ADMIN, json={"stock": 99})
    assert r.status_code == 422


def test_renombrar_y_cambiar_de_proveedor(api: TestClient, proveedor: dict) -> None:
    rep = _crear_repuesto(api, proveedor["proveedor_id"])
    otro = api.post("/proveedores", headers=ADMIN,
                    json={"nombre": _nombre("Destino"), "contacto": "x"}).json()
    r = api.patch(f"/repuestos/{rep['repuesto_id']}", headers=ADMIN,
                  json={"nombre": "Disco ventilado", "proveedor_id": otro["proveedor_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["proveedor_nombre"] == otro["nombre"] and r.json()["nombre"] == "Disco ventilado"
    assert api.get(f"/proveedores/{otro['proveedor_id']}", headers=ADMIN).json()["cantidad_repuestos"] == 1


def test_mover_a_un_proveedor_que_ya_tiene_ese_nombre_es_409(api: TestClient, proveedor: dict) -> None:
    rep = _crear_repuesto(api, proveedor["proveedor_id"])
    otro = api.post("/proveedores", headers=ADMIN,
                    json={"nombre": _nombre("Destino"), "contacto": "x"}).json()
    _crear_repuesto(api, otro["proveedor_id"], nombre=rep["nombre"])
    r = api.patch(f"/repuestos/{rep['repuesto_id']}", headers=ADMIN,
                  json={"proveedor_id": otro["proveedor_id"]})
    assert r.status_code == 409


def test_bajo_umbral_usa_el_particular_o_el_general(api: TestClient, db: Session, proveedor: dict) -> None:
    fabricas.umbral_general_vigente(db, valor=5)
    pid = proveedor["proveedor_id"]
    a = _crear_repuesto(api, pid, nombre="A", stock_inicial=2)                         # 2 < 5 general
    b = _crear_repuesto(api, pid, nombre="B", stock_inicial=8)                         # 8 >= 5
    c = _crear_repuesto(api, pid, nombre="C", stock_inicial=8, umbral_particular=10)   # 8 < 10
    d = _crear_repuesto(api, pid, nombre="D", stock_inicial=2, umbral_particular=0)    # 2 >= 0
    pagina = api.get(f"/repuestos?proveedor_id={pid}&bajo_umbral=true", headers=MECANICO).json()
    assert pagina["umbral_general"] == 5
    assert [r["nombre"] for r in pagina["repuestos"]] == ["A", "C"]
    todos = api.get(f"/repuestos?proveedor_id={pid}", headers=MECANICO).json()
    assert {r["nombre"]: r["umbral_efectivo"] for r in todos["repuestos"]} == \
           {"A": 5, "B": 5, "C": 10, "D": 0}
    assert {b["repuesto_id"], d["repuesto_id"]}.isdisjoint(
        {r["repuesto_id"] for r in pagina["repuestos"]}) and a and c


def test_buscar_repuestos_por_texto(api: TestClient, proveedor: dict) -> None:
    marca = uuid.uuid4().hex[:8]
    _crear_repuesto(api, proveedor["proveedor_id"], nombre=f"Filtro aire {marca}")
    _crear_repuesto(api, proveedor["proveedor_id"], nombre=f"Filtro aceite {marca}")
    _crear_repuesto(api, proveedor["proveedor_id"], nombre=f"Bujía {marca}")
    pagina = api.get(f"/repuestos?q=FILTRO%20A&proveedor_id={proveedor['proveedor_id']}",
                     headers=ADMIN).json()
    assert [r["nombre"] for r in pagina["repuestos"]] == [f"Filtro aceite {marca}", f"Filtro aire {marca}"]


def test_eliminar_repuesto_sin_uso(api: TestClient, db: Session, proveedor: dict) -> None:
    rep = _crear_repuesto(api, proveedor["proveedor_id"])
    assert api.delete(f"/repuestos/{rep['repuesto_id']}", headers=ADMIN).status_code == 204
    assert db.get(Repuesto, rep["repuesto_id"]) is None


@pytest.mark.parametrize("uso", ["stock_inicial", "umbral", "presupuesto"])
def test_repuesto_con_historial_no_se_elimina(
    api: TestClient, db: Session, proveedor: dict, uso: str
) -> None:
    extra = {"stock_inicial": {"stock_inicial": 1}, "umbral": {"umbral_particular": 2}}.get(uso, {})
    rep = _crear_repuesto(api, proveedor["proveedor_id"], **extra)
    if uso == "presupuesto":
        api.post("/presupuestos", headers=MECANICO, json={
            "orden_id": fabricas.nuevo_orden_id(),
            "items": [{"tipo": "repuesto", "repuesto_id": rep["repuesto_id"],
                       "descripcion": "x", "cantidad": "1"}]})
    db.commit()
    r = api.delete(f"/repuestos/{rep['repuesto_id']}", headers=ADMIN)
    assert r.status_code == 409 and "trazabilidad" in r.json()["detail"]
    assert db.get(Repuesto, rep["repuesto_id"]) is not None


def test_repuesto_inexistente_es_404(api: TestClient) -> None:
    for metodo in ("get", "delete"):
        assert api.request(metodo, "/repuestos/987654321", headers=ADMIN).status_code == 404
    assert api.patch("/repuestos/987654321", headers=ADMIN, json={"nombre": "x"}).status_code == 404


# ==================================================================== ACCESO ==

@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), [
    ("post", "/proveedores", {"nombre": "X", "contacto": "y"}),
    ("patch", "/proveedores/1", {"contacto": "y"}),
    ("delete", "/proveedores/1", None),
    ("post", "/repuestos", {"proveedor_id": 1, "nombre": "X"}),
    ("patch", "/repuestos/1", {"nombre": "X"}),
    ("delete", "/repuestos/1", None),
])
def test_solo_el_administrador_escribe(api: TestClient, metodo: str, ruta: str, cuerpo) -> None:
    for cabecera in (MECANICO, CLIENTE):
        assert api.request(metodo, ruta, json=cuerpo, headers=cabecera).status_code == 403
    assert api.request(metodo, ruta, json=cuerpo).status_code == 401


@pytest.mark.parametrize("ruta", ["/proveedores", "/proveedores/1", "/repuestos", "/repuestos/1"])
def test_el_cliente_no_ve_el_catalogo(api: TestClient, ruta: str) -> None:
    assert api.get(ruta, headers=CLIENTE).status_code == 403


def test_se_puede_presupuestar_con_un_repuesto_recien_creado(api: TestClient, proveedor: dict) -> None:
    """Integración con presupuestos: el ítem muestra nombre y proveedor del catálogo."""
    rep = _crear_repuesto(api, proveedor["proveedor_id"], stock_inicial=4)
    r = api.post("/presupuestos", headers=MECANICO, json={
        "orden_id": fabricas.nuevo_orden_id(),
        "items": [{"tipo": "repuesto", "repuesto_id": rep["repuesto_id"], "descripcion": "Disco",
                   "cantidad": "2", "precio_unitario": "45000"}]})
    assert r.status_code == 201, r.text
    item = r.json()["versiones"][0]["items"][0]
    assert item["repuesto_nombre"] == rep["nombre"] and item["proveedor_nombre"] == proveedor["nombre"]


def test_sql_directo_con_stock_negativo_sigue_rechazado(db: Session, proveedor: dict) -> None:
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("insert into repuesto (proveedor_id, nombre, stock) values (:p, 'Neg', -1)"),
                   {"p": proveedor["proveedor_id"]})
