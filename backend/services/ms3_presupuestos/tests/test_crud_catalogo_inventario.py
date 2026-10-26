"""Pruebas CRUD de proveedores, repuestos e inventario (MS3) contra PostgreSQL.

Recorren el ciclo de vida completo de cada recurso por HTTP y comprueban,
después de cada paso, lo que quedó en la base:

    proveedores   crear → leer → listar → modificar → eliminar → 404
    repuestos     crear → leer → listar → modificar → eliminar → 404
    inventario    crear movimientos → leer stock y movimientos; los
                  movimientos son auditoría: no se modifican ni se borran.

Además: validaciones (422), ids inválidos, recursos inexistentes (404) y
peticiones sin token (401). Cada prueba corre en una transacción que se
revierte, con nombres únicos para no chocar con la semilla.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import (
    HistorialUmbral,
    MovimientoInventario,
    ParametroInventario,
    Proveedor,
    Repuesto,
)
from shared.auth import NombreRol, crear_token_acceso


def _cabecera(rol: NombreRol, usuario_id: int) -> dict[str, str]:
    token = crear_token_acceso(
        usuario_id=usuario_id, roles=[rol],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


ADMIN = _cabecera(NombreRol.ADMINISTRADOR, datos.ADMIN_ID)
MECANICO = _cabecera(NombreRol.MECANICO, datos.MECANICO_ID)


def _nombre(base: str) -> str:
    return f"{base} {uuid.uuid4().hex[:8]}"


def _clave() -> str:
    return f"crud-{uuid.uuid4().hex}"


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


def _crear_proveedor(api: TestClient, nombre: str | None = None) -> dict:
    r = api.post("/proveedores", headers=ADMIN,
                 json={"nombre": nombre or _nombre("Proveedor CRUD"), "contacto": "crud@prueba.cl"})
    assert r.status_code == 201, r.text
    return r.json()


def _crear_repuesto(api: TestClient, proveedor_id: int, nombre: str | None = None, **extra) -> dict:
    r = api.post("/repuestos", headers=ADMIN,
                 json={"proveedor_id": proveedor_id, "nombre": nombre or _nombre("Repuesto CRUD"),
                       **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _mover(api: TestClient, repuesto_id: int, tipo: str, cantidad: int,
           orden_id: int | None = None, clave: str | None = None):
    cuerpo = {"clave_operacion": clave or _clave(), "repuesto_id": repuesto_id,
              "tipo": tipo, "cantidad": cantidad}
    if orden_id is not None:
        cuerpo["orden_id"] = orden_id
    cabecera = ADMIN if tipo in ("ingreso", "ajuste") else MECANICO
    return api.post("/inventario/movimientos", headers=cabecera, json=cuerpo)


def _umbral_general(db: Session, valor: int) -> None:
    """Deja un umbral general vigente conocido (dentro de la transacción de prueba)."""
    vigente = db.scalars(select(ParametroInventario)
                         .where(ParametroInventario.vigente_hasta.is_(None))).first()
    if vigente is not None:
        vigente.umbral_general = valor
    else:
        db.add(ParametroInventario(umbral_general=valor, actualizado_por_id=datos.ADMIN_ID))
    db.flush()


# ================================================================ PROVEEDORES ==

def test_ciclo_crud_completo_de_proveedor(api: TestClient, db: Session) -> None:
    nombre = _nombre("Lubricentro Norte")

    # Crear
    creado = _crear_proveedor(api, nombre)
    pid = creado["proveedor_id"]
    assert creado == {"proveedor_id": pid, "nombre": nombre,
                      "contacto": "crud@prueba.cl", "tipo_distribuidor": "generico",
                      "cantidad_repuestos": 0}
    assert db.get(Proveedor, pid).nombre == nombre

    # Leer (detalle) y listar
    detalle = api.get(f"/proveedores/{pid}", headers=MECANICO)
    assert detalle.status_code == 200
    assert detalle.json() == {**creado, "repuestos": []}
    listado = api.get("/proveedores", params={"q": nombre}, headers=MECANICO).json()
    assert [p["proveedor_id"] for p in listado["proveedores"]] == [pid]

    # Modificar ambos campos
    r = api.patch(f"/proveedores/{pid}", headers=ADMIN,
                  json={"nombre": f"{nombre} Ltda", "contacto": "+56 9 5555 0000"})
    assert r.status_code == 200
    assert r.json()["nombre"] == f"{nombre} Ltda" and r.json()["contacto"] == "+56 9 5555 0000"
    db.expire_all()
    guardado = db.get(Proveedor, pid)
    assert (guardado.nombre, guardado.contacto) == (f"{nombre} Ltda", "+56 9 5555 0000")
    assert api.get(f"/proveedores/{pid}", headers=MECANICO).json()["nombre"] == f"{nombre} Ltda"

    # Eliminar
    assert api.delete(f"/proveedores/{pid}", headers=ADMIN).status_code == 204
    db.expire_all()
    assert db.get(Proveedor, pid) is None

    # Después de eliminado: todo responde 404 y ya no aparece en el listado
    assert api.get(f"/proveedores/{pid}", headers=MECANICO).status_code == 404
    assert api.patch(f"/proveedores/{pid}", headers=ADMIN, json={"contacto": "x"}).status_code == 404
    assert api.delete(f"/proveedores/{pid}", headers=ADMIN).status_code == 404
    assert api.get("/proveedores", params={"q": nombre}, headers=MECANICO).json()["total"] == 0


def test_modificacion_parcial_conserva_lo_no_enviado(api: TestClient) -> None:
    creado = _crear_proveedor(api)
    r = api.patch(f"/proveedores/{creado['proveedor_id']}", headers=ADMIN,
                  json={"nombre": f"  {creado['nombre']} Sur  "})
    assert r.status_code == 200
    # Se recortan los espacios y el contacto sigue igual.
    assert r.json()["nombre"] == f"{creado['nombre']} Sur"
    assert r.json()["contacto"] == creado["contacto"]


@pytest.mark.parametrize("cuerpo", [
    {"contacto": "falta nombre"},
    {"nombre": "Falta contacto"},
    {"nombre": "", "contacto": "x"},
    {"nombre": "   ", "contacto": "x"},
    {"nombre": "x" * 121, "contacto": "x"},
    {"nombre": "Contacto largo", "contacto": "x" * 201},
    {"nombre": "Con id", "contacto": "x", "proveedor_id": 99},
], ids=["sin-nombre", "sin-contacto", "nombre-vacio", "nombre-espacios",
        "nombre-largo", "contacto-largo", "campo-extra"])
def test_crear_proveedor_invalido_es_422_y_no_guarda_nada(
    api: TestClient, db: Session, cuerpo: dict
) -> None:
    antes = db.query(Proveedor).count()
    assert api.post("/proveedores", headers=ADMIN, json=cuerpo).status_code == 422
    assert db.query(Proveedor).count() == antes


@pytest.mark.parametrize("cuerpo", [
    {"nombre": ""}, {"contacto": "x" * 201}, {"cantidad_repuestos": 5}, {"nombre": None},
])
def test_modificar_proveedor_invalido_es_422_y_no_cambia(api: TestClient, cuerpo: dict) -> None:
    creado = _crear_proveedor(api)
    pid = creado["proveedor_id"]
    assert api.patch(f"/proveedores/{pid}", headers=ADMIN, json=cuerpo).status_code == 422
    assert api.get(f"/proveedores/{pid}", headers=MECANICO).json()["nombre"] == creado["nombre"]


@pytest.mark.parametrize("ident", ["0", "-1", "abc"])
def test_ids_de_proveedor_invalidos_son_422(api: TestClient, ident: str) -> None:
    assert api.get(f"/proveedores/{ident}", headers=MECANICO).status_code == 422
    assert api.patch(f"/proveedores/{ident}", headers=ADMIN, json={"contacto": "x"}).status_code == 422
    assert api.delete(f"/proveedores/{ident}", headers=ADMIN).status_code == 422


def test_detalle_de_proveedor_lista_sus_repuestos_ordenados(api: TestClient) -> None:
    proveedor = _crear_proveedor(api)
    pid = proveedor["proveedor_id"]
    for nombre in ("filtro de aire", "Bujía", "amortiguador"):
        _crear_repuesto(api, pid, nombre)
    detalle = api.get(f"/proveedores/{pid}", headers=MECANICO).json()
    assert detalle["cantidad_repuestos"] == 3
    assert [r["nombre"] for r in detalle["repuestos"]] == ["amortiguador", "Bujía", "filtro de aire"]
    assert all(r["proveedor_id"] == pid for r in detalle["repuestos"])


def test_proveedor_que_abastecio_repuestos_no_se_elimina(api: TestClient, db: Session) -> None:
    """Trazabilidad (0007_ms3): aunque ya no tenga repuestos, queda en su historial."""
    origen = _crear_proveedor(api)
    destino = _crear_proveedor(api)
    repuesto = _crear_repuesto(api, origen["proveedor_id"])

    assert api.delete(f"/proveedores/{origen['proveedor_id']}", headers=ADMIN).status_code == 409
    r = api.patch(f"/repuestos/{repuesto['repuesto_id']}", headers=ADMIN,
                  json={"proveedor_id": destino["proveedor_id"]})
    assert r.status_code == 200 and r.json()["proveedor_nombre"] == destino["nombre"]

    r = api.delete(f"/proveedores/{origen['proveedor_id']}", headers=ADMIN)
    assert r.status_code == 409 and "trazabilidad" in r.json()["detail"]
    db.expire_all()
    assert db.get(Repuesto, repuesto["repuesto_id"]).proveedor_id == destino["proveedor_id"]
    assert db.get(Proveedor, origen["proveedor_id"]) is not None


# ================================================================== REPUESTOS ==

def test_ciclo_crud_completo_de_repuesto(api: TestClient, db: Session) -> None:
    proveedor = _crear_proveedor(api)
    pid = proveedor["proveedor_id"]
    nombre = _nombre("Pastilla de freno")

    # Crear
    creado = _crear_repuesto(api, pid, nombre, umbral_particular=4)
    rid = creado["repuesto_id"]
    assert creado["nombre"] == nombre and creado["proveedor_id"] == pid
    assert creado["proveedor_nombre"] == proveedor["nombre"]
    assert (creado["stock"], creado["umbral_particular"], creado["umbral_efectivo"]) == (0, 4, 4)
    assert creado["bajo_umbral"] is True
    assert db.get(Repuesto, rid).nombre == nombre

    # Leer y listar
    assert api.get(f"/repuestos/{rid}", headers=MECANICO).json() == creado
    listado = api.get("/repuestos", params={"proveedor_id": pid}, headers=MECANICO).json()
    assert [r["repuesto_id"] for r in listado["repuestos"]] == [rid] and listado["total"] == 1
    assert api.get(f"/proveedores/{pid}", headers=MECANICO).json()["cantidad_repuestos"] == 1

    # Modificar nombre y umbral
    r = api.patch(f"/repuestos/{rid}", headers=ADMIN,
                  json={"nombre": f"{nombre} cerámica", "umbral_particular": 0,
                        "observacion": "Ya no se repone"})
    assert r.status_code == 200
    assert r.json()["nombre"] == f"{nombre} cerámica"
    assert (r.json()["umbral_efectivo"], r.json()["bajo_umbral"]) == (0, False)
    db.expire_all()
    assert db.get(Repuesto, rid).umbral_particular == 0
    assert api.get(f"/repuestos/{rid}", headers=MECANICO).json() == r.json()

    # Eliminar: cambió el umbral, así que tiene historial y se conserva (409).
    assert api.delete(f"/repuestos/{rid}", headers=ADMIN).status_code == 409
    assert db.get(Repuesto, rid) is not None


def test_eliminar_repuesto_lo_quita_del_proveedor_y_responde_404_despues(
    api: TestClient, db: Session
) -> None:
    proveedor = _crear_proveedor(api)
    pid = proveedor["proveedor_id"]
    rid = _crear_repuesto(api, pid)["repuesto_id"]

    assert api.delete(f"/repuestos/{rid}", headers=ADMIN).status_code == 204
    db.expire_all()
    assert db.get(Repuesto, rid) is None
    assert api.get(f"/repuestos/{rid}", headers=MECANICO).status_code == 404
    assert api.patch(f"/repuestos/{rid}", headers=ADMIN, json={"nombre": "x"}).status_code == 404
    assert api.delete(f"/repuestos/{rid}", headers=ADMIN).status_code == 404
    assert api.get(f"/inventario/stock/{rid}", headers=MECANICO).status_code == 404
    assert api.get(f"/proveedores/{pid}", headers=MECANICO).json()["cantidad_repuestos"] == 0


def test_umbral_null_vuelve_al_general_y_queda_en_historial(api: TestClient, db: Session) -> None:
    _umbral_general(db, 7)
    proveedor = _crear_proveedor(api)
    creado = _crear_repuesto(api, proveedor["proveedor_id"], stock_inicial=5, umbral_particular=2)
    rid = creado["repuesto_id"]
    assert (creado["umbral_efectivo"], creado["bajo_umbral"]) == (2, False)

    r = api.patch(f"/repuestos/{rid}", headers=ADMIN,
                  json={"umbral_particular": None, "observacion": "Usar el general"})
    assert r.status_code == 200
    assert r.json()["umbral_particular"] is None
    assert (r.json()["umbral_efectivo"], r.json()["bajo_umbral"]) == (7, True)

    ultimo = db.scalars(select(HistorialUmbral).where(HistorialUmbral.repuesto_id == rid)
                        .order_by(HistorialUmbral.historial_id.desc())).first()
    assert (ultimo.valor_anterior, ultimo.valor_nuevo, ultimo.observacion) == (2, None, "Usar el general")


def test_modificar_solo_el_nombre_no_toca_umbral_ni_stock(api: TestClient, db: Session) -> None:
    proveedor = _crear_proveedor(api)
    creado = _crear_repuesto(api, proveedor["proveedor_id"], stock_inicial=3, umbral_particular=1)
    rid = creado["repuesto_id"]
    historial_antes = db.query(HistorialUmbral).filter(HistorialUmbral.repuesto_id == rid).count()

    r = api.patch(f"/repuestos/{rid}", headers=ADMIN, json={"nombre": _nombre("Renombrado")})
    assert r.status_code == 200
    assert (r.json()["stock"], r.json()["umbral_particular"]) == (3, 1)
    assert db.query(HistorialUmbral).filter(HistorialUmbral.repuesto_id == rid).count() == historial_antes


def test_mover_a_proveedor_inexistente_es_404_y_no_cambia(api: TestClient) -> None:
    proveedor = _crear_proveedor(api)
    creado = _crear_repuesto(api, proveedor["proveedor_id"])
    rid = creado["repuesto_id"]
    r = api.patch(f"/repuestos/{rid}", headers=ADMIN,
                  json={"proveedor_id": 999_999_999, "nombre": "No debe quedar"})
    assert r.status_code == 404
    assert api.get(f"/repuestos/{rid}", headers=MECANICO).json() == creado


@pytest.mark.parametrize("cuerpo", [
    {"observacion": "solo observación"},
    {"nombre": ""},
    {"nombre": "x" * 121},
    {"umbral_particular": -1},
    {"proveedor_id": 0},
    {"stock": 50},
], ids=["solo-observacion", "nombre-vacio", "nombre-largo", "umbral-negativo",
        "proveedor-cero", "stock-directo"])
def test_modificar_repuesto_invalido_es_422_y_no_cambia(api: TestClient, cuerpo: dict) -> None:
    proveedor = _crear_proveedor(api)
    creado = _crear_repuesto(api, proveedor["proveedor_id"], stock_inicial=2)
    rid = creado["repuesto_id"]
    assert api.patch(f"/repuestos/{rid}", headers=ADMIN, json=cuerpo).status_code == 422
    assert api.get(f"/repuestos/{rid}", headers=MECANICO).json() == creado


@pytest.mark.parametrize("ident", ["0", "-5", "abc"])
def test_ids_de_repuesto_invalidos_son_422(api: TestClient, ident: str) -> None:
    assert api.get(f"/repuestos/{ident}", headers=MECANICO).status_code == 422
    assert api.patch(f"/repuestos/{ident}", headers=ADMIN, json={"nombre": "x"}).status_code == 422
    assert api.delete(f"/repuestos/{ident}", headers=ADMIN).status_code == 422
    assert api.get(f"/inventario/stock/{ident}", headers=MECANICO).status_code == 422


# ================================================================= INVENTARIO ==

def test_crear_y_leer_movimientos_mantiene_el_stock_consistente(api: TestClient, db: Session) -> None:
    proveedor = _crear_proveedor(api)
    rid = _crear_repuesto(api, proveedor["proveedor_id"])["repuesto_id"]
    orden = 900_001

    pasos = [("ingreso", 10, None), ("compromiso", 3, orden), ("consumo", 2, orden),
             ("liberacion", 1, orden), ("ajuste", -2, None)]
    creados = []
    for tipo, cantidad, orden_id in pasos:
        r = _mover(api, rid, tipo, cantidad, orden_id)
        assert r.status_code == 201, r.text
        mov = r.json()["movimiento"]
        assert (mov["tipo"], mov["cantidad"], mov["orden_id"]) == (tipo, cantidad, orden_id)
        creados.append(mov)

    # Stock físico: 10 − 2 (consumo) − 2 (ajuste). Lo comprometido: 3 − 2 − 1 = 0.
    stock = api.get(f"/inventario/stock/{rid}", headers=MECANICO).json()
    assert (stock["stock"], stock["comprometido"], stock["disponible"]) == (6, 0, 6)
    assert stock["compromisos"] == []
    db.expire_all()
    assert db.get(Repuesto, rid).stock == 6
    assert api.get(f"/repuestos/{rid}", headers=MECANICO).json()["stock"] == 6

    # Leer: el listado devuelve exactamente lo creado, del más reciente al más antiguo.
    pagina = api.get("/inventario/movimientos", params={"repuesto_id": rid}, headers=MECANICO).json()
    assert pagina["total"] == len(pasos)
    assert pagina["movimientos"] == list(reversed(creados))
    registrados_por = {m["tipo"]: m["registrado_por_id"] for m in pagina["movimientos"]}
    assert registrados_por["ingreso"] == datos.ADMIN_ID
    assert registrados_por["consumo"] == datos.MECANICO_ID
    guardados = db.scalars(select(MovimientoInventario)
                           .where(MovimientoInventario.repuesto_id == rid)).all()
    assert {m.movimiento_id for m in guardados} == {m["movimiento_id"] for m in creados}


def test_compromiso_abierto_se_ve_en_el_stock_por_orden(api: TestClient) -> None:
    proveedor = _crear_proveedor(api)
    rid = _crear_repuesto(api, proveedor["proveedor_id"], stock_inicial=8)["repuesto_id"]
    assert _mover(api, rid, "compromiso", 3, 900_101).status_code == 201
    assert _mover(api, rid, "compromiso", 2, 900_102).status_code == 201

    stock = api.get(f"/inventario/stock/{rid}", headers=MECANICO).json()
    assert (stock["stock"], stock["comprometido"], stock["disponible"]) == (8, 5, 3)
    assert stock["compromisos"] == [{"orden_id": 900_101, "comprometido": 3},
                                    {"orden_id": 900_102, "comprometido": 2}]


def test_listado_de_movimientos_pagina_y_filtra(api: TestClient) -> None:
    proveedor = _crear_proveedor(api)
    rid = _crear_repuesto(api, proveedor["proveedor_id"])["repuesto_id"]
    for cantidad in (1, 2, 3, 4, 5):
        assert _mover(api, rid, "ingreso", cantidad).status_code == 201

    base = {"repuesto_id": rid, "limite": 2}
    p1 = api.get("/inventario/movimientos", params=base, headers=MECANICO).json()
    p3 = api.get("/inventario/movimientos", params={**base, "desde": 4}, headers=MECANICO).json()
    assert p1["total"] == p3["total"] == 5
    assert [m["cantidad"] for m in p1["movimientos"]] == [5, 4]
    assert [m["cantidad"] for m in p3["movimientos"]] == [1]
    vacio = api.get("/inventario/movimientos", params={"repuesto_id": rid, "tipo": "consumo"},
                    headers=MECANICO).json()
    assert vacio == {"total": 0, "desde": 0, "limite": 50, "movimientos": []}
    assert api.get("/inventario/movimientos", params={"tipo": "robo"},
                   headers=MECANICO).status_code == 422


def test_los_movimientos_no_se_modifican_ni_se_borran(api: TestClient, db: Session) -> None:
    proveedor = _crear_proveedor(api)
    rid = _crear_repuesto(api, proveedor["proveedor_id"])["repuesto_id"]
    mov = _mover(api, rid, "ingreso", 4).json()["movimiento"]
    mid = mov["movimiento_id"]

    for metodo in ("put", "patch", "delete"):
        assert getattr(api, metodo)("/inventario/movimientos", headers=ADMIN).status_code == 405
        assert getattr(api, metodo)(f"/inventario/movimientos/{mid}", headers=ADMIN).status_code \
            in (404, 405)
    assert api.delete(f"/inventario/stock/{rid}", headers=ADMIN).status_code == 405

    db.expire_all()
    guardado = db.get(MovimientoInventario, mid)
    assert (guardado.tipo, guardado.cantidad) == ("ingreso", 4)
    assert db.get(Repuesto, rid).stock == 4


def test_movimiento_rechazado_no_deja_rastro(api: TestClient, db: Session) -> None:
    proveedor = _crear_proveedor(api)
    rid = _crear_repuesto(api, proveedor["proveedor_id"], stock_inicial=2)["repuesto_id"]
    antes = db.query(MovimientoInventario).filter(MovimientoInventario.repuesto_id == rid).count()

    assert _mover(api, rid, "consumo", 5, 900_201).status_code == 409   # sin stock
    assert _mover(api, rid, "consumo", 0, 900_201).status_code == 422   # cantidad inválida
    assert _mover(api, 999_999_999, "ingreso", 1).status_code == 404   # repuesto inexistente

    db.expire_all()
    assert db.query(MovimientoInventario).filter(MovimientoInventario.repuesto_id == rid).count() == antes
    assert db.get(Repuesto, rid).stock == 2


# ============================================================ AUTENTICACIÓN ==

@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), [
    ("get", "/proveedores", None),
    ("get", "/proveedores/1", None),
    ("post", "/proveedores", {"nombre": "x", "contacto": "y"}),
    ("patch", "/proveedores/1", {"contacto": "y"}),
    ("delete", "/proveedores/1", None),
    ("get", "/repuestos", None),
    ("get", "/repuestos/1", None),
    ("post", "/repuestos", {"proveedor_id": 1, "nombre": "x"}),
    ("patch", "/repuestos/1", {"nombre": "x"}),
    ("delete", "/repuestos/1", None),
    ("get", "/inventario/movimientos", None),
    ("post", "/inventario/movimientos", {"clave_operacion": "sin-token-1", "repuesto_id": 1,
                                         "tipo": "ingreso", "cantidad": 1}),
    ("get", "/inventario/stock/1", None),
])
def test_sin_token_es_401(api: TestClient, metodo: str, ruta: str, cuerpo) -> None:
    kwargs = {"json": cuerpo} if cuerpo is not None else {}
    assert getattr(api, metodo)(ruta, **kwargs).status_code == 401


def test_token_invalido_es_401(api: TestClient) -> None:
    falso = {"Authorization": "Bearer no-es-un-jwt"}
    assert api.get("/repuestos", headers=falso).status_code == 401
    assert api.post("/proveedores", headers=falso, json={"nombre": "x", "contacto": "y"}).status_code == 401
