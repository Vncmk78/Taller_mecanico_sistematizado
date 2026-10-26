"""Trazabilidad Repuesto–Proveedor/Distribuidor (migración 0007_ms3).

- tipo de distribuidor (oficial / genérico) en proveedores;
- historial de proveedores de cada repuesto (alta y cambios, con quién y por qué);
- proveedor que entregó cada ingreso de stock, aunque el repuesto cambie de proveedor;
- GET /repuestos/{id}/trazabilidad y GET /proveedores/{id}/trazabilidad;
- la base exige proveedor en los ingresos y solo en ellos.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import (
    HistorialProveedorRepuesto,
    MovimientoInventario,
    Proveedor,
)
from services.ms3_presupuestos.tests import fabricas
from shared.auth import NombreRol, crear_token_acceso


def _cabecera(rol: NombreRol, usuario_id: int) -> dict[str, str]:
    return {"Authorization": "Bearer " + crear_token_acceso(
        usuario_id=usuario_id, roles=[rol],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256")}


ADMIN = _cabecera(NombreRol.ADMINISTRADOR, datos.ADMIN_ID)
MECANICO = _cabecera(NombreRol.MECANICO, datos.MECANICO_ID)
CLIENTE = _cabecera(NombreRol.CLIENTE, datos.CLIENTE_ID)


def _nombre(base: str) -> str:
    return f"{base} {uuid.uuid4().hex[:8]}"


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


def _proveedor(api: TestClient, tipo: str | None = None) -> dict:
    cuerpo = {"nombre": _nombre("Distribuidora"), "contacto": "ventas@x.cl"}
    if tipo:
        cuerpo["tipo_distribuidor"] = tipo
    r = api.post("/proveedores", headers=ADMIN, json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


def _repuesto(api: TestClient, proveedor_id: int, **extra) -> dict:
    r = api.post("/repuestos", headers=ADMIN,
                 json={"proveedor_id": proveedor_id, "nombre": _nombre("Bomba"), **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _ingreso(api: TestClient, repuesto_id: int, cantidad: int, proveedor_id: int | None = None):
    cuerpo = {"clave_operacion": f"traza-{uuid.uuid4().hex}", "repuesto_id": repuesto_id,
              "tipo": "ingreso", "cantidad": cantidad}
    if proveedor_id:
        cuerpo["proveedor_id"] = proveedor_id
    return api.post("/inventario/movimientos", headers=ADMIN, json=cuerpo)


# ======================================================= tipo de distribuidor ==

def test_tipo_de_distribuidor_por_defecto_generico_y_se_puede_cambiar(api: TestClient) -> None:
    generico = _proveedor(api)
    oficial = _proveedor(api, "oficial")
    assert (generico["tipo_distribuidor"], oficial["tipo_distribuidor"]) == ("generico", "oficial")

    r = api.patch(f"/proveedores/{generico['proveedor_id']}", headers=ADMIN,
                  json={"tipo_distribuidor": "oficial"})
    assert r.status_code == 200 and r.json()["tipo_distribuidor"] == "oficial"
    assert api.post("/proveedores", headers=ADMIN, json={
        "nombre": _nombre("X"), "contacto": "x", "tipo_distribuidor": "pirata"}).status_code == 422


def test_filtrar_proveedores_por_tipo(api: TestClient) -> None:
    marca = uuid.uuid4().hex[:8]
    for tipo in ("oficial", "generico", "oficial"):
        api.post("/proveedores", headers=ADMIN,
                 json={"nombre": f"Prov {marca} {tipo} {uuid.uuid4().hex[:4]}", "contacto": "x",
                       "tipo_distribuidor": tipo})
    oficiales = api.get("/proveedores", params={"q": marca, "tipo_distribuidor": "oficial"},
                        headers=MECANICO).json()
    assert oficiales["total"] == 2
    assert {p["tipo_distribuidor"] for p in oficiales["proveedores"]} == {"oficial"}


def test_el_repuesto_muestra_el_tipo_de_su_distribuidor(api: TestClient) -> None:
    oficial = _proveedor(api, "oficial")
    rep = _repuesto(api, oficial["proveedor_id"])
    assert rep["proveedor_tipo_distribuidor"] == "oficial"


# ================================================= historial de proveedores ==

def test_alta_y_cambios_de_proveedor_quedan_en_el_historial(api: TestClient) -> None:
    a, b, c = _proveedor(api, "oficial"), _proveedor(api), _proveedor(api)
    rid = _repuesto(api, a["proveedor_id"])["repuesto_id"]

    api.patch(f"/repuestos/{rid}", headers=ADMIN,
              json={"proveedor_id": b["proveedor_id"], "observacion": "A dejó de importarlo"})
    api.patch(f"/repuestos/{rid}", headers=ADMIN, json={"proveedor_id": c["proveedor_id"]})
    # Cambiar solo el nombre no es un cambio de proveedor.
    api.patch(f"/repuestos/{rid}", headers=ADMIN, json={"nombre": _nombre("Renombrado")})

    t = api.get(f"/repuestos/{rid}/trazabilidad", headers=MECANICO).json()
    pasos = [((h["proveedor_anterior"] or {}).get("proveedor_id"), h["proveedor_nuevo"]["proveedor_id"],
              h["registrado_por_id"], h["observacion"]) for h in t["historial_proveedores"]]
    assert pasos == [
        (None, a["proveedor_id"], datos.ADMIN_ID, "Alta del repuesto"),
        (a["proveedor_id"], b["proveedor_id"], datos.ADMIN_ID, "A dejó de importarlo"),
        (b["proveedor_id"], c["proveedor_id"], datos.ADMIN_ID, None),
    ]
    assert t["proveedor_actual"]["proveedor_id"] == c["proveedor_id"]
    assert t["historial_proveedores"][0]["proveedor_nuevo"]["tipo_distribuidor"] == "oficial"


def test_un_repuesto_creado_por_cualquier_via_registra_su_alta(db: Session) -> None:
    """El historial lo escribe el modelo: también la semilla y las pruebas."""
    r = fabricas.nuevo_repuesto(db)
    filas = db.scalars(select(HistorialProveedorRepuesto)
                       .where(HistorialProveedorRepuesto.repuesto_id == r.repuesto_id)).all()
    assert [(f.proveedor_anterior_id, f.proveedor_nuevo_id) for f in filas] == [(None, r.proveedor_id)]


# ===================================================== proveedor de ingresos ==

def test_cada_ingreso_guarda_quien_entrego_las_unidades(api: TestClient) -> None:
    a, b = _proveedor(api, "oficial"), _proveedor(api)
    rid = _repuesto(api, a["proveedor_id"], stock_inicial=4)["repuesto_id"]

    # Compra puntual a otro distribuidor sin cambiar el proveedor habitual.
    puntual = _ingreso(api, rid, 2, proveedor_id=b["proveedor_id"])
    assert puntual.status_code == 201 and puntual.json()["movimiento"]["proveedor_id"] == b["proveedor_id"]
    # Luego el repuesto pasa a B y llega más stock.
    api.patch(f"/repuestos/{rid}", headers=ADMIN, json={"proveedor_id": b["proveedor_id"]})
    assert _ingreso(api, rid, 5).json()["movimiento"]["proveedor_id"] == b["proveedor_id"]

    t = api.get(f"/repuestos/{rid}/trazabilidad", headers=MECANICO).json()
    por_proveedor = {i["proveedor"]["proveedor_id"]: (i["ingresos"], i["unidades"])
                     for i in t["ingresos_por_proveedor"]}
    # Las 4 iniciales siguen siendo de A aunque hoy lo abastezca B.
    assert por_proveedor == {a["proveedor_id"]: (1, 4), b["proveedor_id"]: (2, 7)}
    assert t["repuesto"]["stock"] == 11

    solo_a = api.get("/inventario/movimientos", params={"proveedor_id": a["proveedor_id"]},
                     headers=MECANICO).json()
    assert [(m["repuesto_id"], m["cantidad"]) for m in solo_a["movimientos"]] == [(rid, 4)]


def test_ingreso_con_proveedor_inexistente_es_404(api: TestClient) -> None:
    rid = _repuesto(api, _proveedor(api)["proveedor_id"])["repuesto_id"]
    assert _ingreso(api, rid, 1, proveedor_id=999_999_992).status_code == 404


def test_solo_un_ingreso_indica_proveedor(api: TestClient) -> None:
    p = _proveedor(api)
    rid = _repuesto(api, p["proveedor_id"], stock_inicial=3)["repuesto_id"]
    r = api.post("/inventario/movimientos", headers=MECANICO, json={
        "clave_operacion": f"traza-{uuid.uuid4().hex}", "repuesto_id": rid, "tipo": "consumo",
        "cantidad": 1, "orden_id": 5, "proveedor_id": p["proveedor_id"]})
    assert r.status_code == 422


def test_la_base_exige_proveedor_en_ingresos_y_solo_en_ellos(db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=5)
    ingreso = fabricas.nuevo_movimiento(db, r, tipo="ingreso", cantidad=1)
    assert ingreso.proveedor_id == r.proveedor_id  # lo completa el modelo

    with pytest.raises(IntegrityError, match="proveedor_solo_en_ingreso"), db.begin_nested():
        db.add(MovimientoInventario(clave_operacion=f"x-{uuid.uuid4().hex}", repuesto=r,
                                    tipo="consumo", cantidad=1, orden_id=9,
                                    proveedor_id=r.proveedor_id, registrado_por_id=2))
        db.flush()


# ========================================================= uso por orden ==

def test_trazabilidad_muestra_reservas_y_consumos_por_orden(api: TestClient) -> None:
    rid = _repuesto(api, _proveedor(api)["proveedor_id"], stock_inicial=10)["repuesto_id"]
    for tipo, cantidad, orden in [("compromiso", 3, 71), ("consumo", 2, 71), ("consumo", 1, 72)]:
        r = api.post("/inventario/movimientos", headers=MECANICO, json={
            "clave_operacion": f"traza-{uuid.uuid4().hex}", "repuesto_id": rid, "tipo": tipo,
            "cantidad": cantidad, "orden_id": orden})
        assert r.status_code == 201, r.text

    uso = api.get(f"/repuestos/{rid}/trazabilidad", headers=MECANICO).json()["uso_por_orden"]
    assert uso == [{"orden_id": 71, "reservado": 1, "consumido": 2},
                   {"orden_id": 72, "reservado": 0, "consumido": 1}]


# ==================================================== vista por proveedor ==

def test_trazabilidad_de_un_proveedor(api: TestClient) -> None:
    a, b = _proveedor(api), _proveedor(api)
    se_fue = _repuesto(api, a["proveedor_id"], stock_inicial=6)
    sigue = _repuesto(api, a["proveedor_id"], stock_inicial=2)
    api.patch(f"/repuestos/{se_fue['repuesto_id']}", headers=ADMIN,
              json={"proveedor_id": b["proveedor_id"]})

    t = api.get(f"/proveedores/{a['proveedor_id']}/trazabilidad", headers=MECANICO).json()
    assert t["unidades_ingresadas"] == 8
    assert {(r["repuesto_id"], r["actual"], r["unidades_ingresadas"]) for r in t["repuestos"]} == {
        (se_fue["repuesto_id"], False, 6), (sigue["repuesto_id"], True, 2)}

    t_b = api.get(f"/proveedores/{b['proveedor_id']}/trazabilidad", headers=MECANICO).json()
    assert [(r["repuesto_id"], r["actual"], r["unidades_ingresadas"]) for r in t_b["repuestos"]] == [
        (se_fue["repuesto_id"], True, 0)]


def test_proveedor_sin_trazabilidad_si_se_elimina(api: TestClient, db: Session) -> None:
    p = _proveedor(api)
    assert api.delete(f"/proveedores/{p['proveedor_id']}", headers=ADMIN).status_code == 204
    assert db.get(Proveedor, p["proveedor_id"]) is None


def test_repuesto_sin_uso_se_elimina_con_su_historial(api: TestClient, db: Session) -> None:
    p = _proveedor(api)
    rid = _repuesto(api, p["proveedor_id"])["repuesto_id"]
    assert api.delete(f"/repuestos/{rid}", headers=ADMIN).status_code == 204
    assert db.scalars(select(HistorialProveedorRepuesto)
                      .where(HistorialProveedorRepuesto.repuesto_id == rid)).all() == []
    # El proveedor ya no figura en ninguna trazabilidad: se puede borrar.
    assert api.delete(f"/proveedores/{p['proveedor_id']}", headers=ADMIN).status_code == 204


@pytest.mark.parametrize("ruta", ["/repuestos/{r}/trazabilidad", "/proveedores/{p}/trazabilidad"])
def test_permisos_y_404(api: TestClient, ruta: str) -> None:
    p = _proveedor(api)
    r = _repuesto(api, p["proveedor_id"])
    url = ruta.format(r=r["repuesto_id"], p=p["proveedor_id"])
    assert api.get(url, headers=ADMIN).status_code == 200
    assert api.get(url, headers=CLIENTE).status_code == 403
    assert api.get(url).status_code == 401
    assert api.get(ruta.format(r=999_999_993, p=999_999_993), headers=ADMIN).status_code == 404
