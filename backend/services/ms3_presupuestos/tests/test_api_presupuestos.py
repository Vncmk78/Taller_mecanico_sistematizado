"""Endpoints iniciales de presupuestos contra PostgreSQL (persistencia ORM real).

La app usa la sesión de prueba (`db`, transacción revertida al final) en lugar
de get_db, así cada petición persiste de verdad (triggers incluidos) y no deja
datos.
"""
from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import Presupuesto, Repuesto
from services.ms3_presupuestos.tests import fabricas
from shared.auth import NombreRol, crear_token_acceso


def _cabecera(*roles: NombreRol, usuario_id: int = datos.MECANICO_ID) -> dict[str, str]:
    token = crear_token_acceso(
        usuario_id=usuario_id, roles=roles,
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


MECANICO = _cabecera(NombreRol.MECANICO)
ADMIN = _cabecera(NombreRol.ADMINISTRADOR, usuario_id=datos.ADMIN_ID)
CLIENTE = _cabecera(NombreRol.CLIENTE, usuario_id=datos.CLIENTE_ID)


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


def _items(catalogo: dict[str, Repuesto]) -> list[dict]:
    pastillas = catalogo["Pastillas de freno delanteras"]
    return [
        {"tipo": "repuesto", "descripcion": "Juego de pastillas", "cantidad": "1",
         "precio_unitario": "38990", "repuesto_id": pastillas.repuesto_id},
        {"tipo": "mano_de_obra", "descripcion": "Cambio de pastillas",
         "cantidad": "1.5", "precio_unitario": "20000"},
    ]


# ------------------------------------------------------------------- crear --

def test_crear_presupuesto_persiste_version_1_en_borrador(
    api: TestClient, db: Session, catalogo: dict[str, Repuesto]
) -> None:
    orden = fabricas.nuevo_orden_id()
    r = api.post("/presupuestos", json={"orden_id": orden, "items": _items(catalogo)},
                 headers=MECANICO)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["orden_id"] == orden
    assert cuerpo["ultima_version"] == 1 and cuerpo["estado_ultima_version"] == "borrador"
    assert Decimal(cuerpo["total_ultima_version"]) == datos.TOTAL_PRESUPUESTO_EJEMPLO
    assert cuerpo["version_vigente"] is None
    v1 = cuerpo["versiones"][0]
    assert v1["creado_por_id"] == datos.MECANICO_ID and v1["enviado_en"] is None
    repuesto = next(i for i in v1["items"] if i["tipo"] == "repuesto")
    pastillas = catalogo["Pastillas de freno delanteras"]
    assert repuesto["repuesto_nombre"] == pastillas.nombre
    assert repuesto["proveedor_nombre"] == pastillas.proveedor.nombre

    # Quedó en la base (ORM): presupuesto → versión → ítems.
    db.expire_all()
    guardado = db.get(Presupuesto, cuerpo["presupuesto_id"])
    assert [v.numero for v in guardado.versiones] == [1]
    assert len(guardado.versiones[0].items) == 2


def test_crear_sin_items_deja_un_borrador_vacio(api: TestClient) -> None:
    r = api.post("/presupuestos", json={"orden_id": fabricas.nuevo_orden_id()}, headers=ADMIN)
    assert r.status_code == 201
    assert r.json()["versiones"][0]["items"] == []
    assert Decimal(r.json()["total_ultima_version"]) == 0


def test_segunda_creacion_para_la_misma_orden_es_409(api: TestClient) -> None:
    cuerpo = {"orden_id": fabricas.nuevo_orden_id()}
    assert api.post("/presupuestos", json=cuerpo, headers=MECANICO).status_code == 201
    r = api.post("/presupuestos", json=cuerpo, headers=ADMIN)
    assert r.status_code == 409
    assert "nueva versión" in r.json()["detail"]


def test_repuesto_inexistente_es_422_y_no_deja_nada(api: TestClient, db: Session) -> None:
    orden = fabricas.nuevo_orden_id()
    r = api.post("/presupuestos", headers=MECANICO, json={"orden_id": orden, "items": [
        {"tipo": "repuesto", "descripcion": "X", "cantidad": "1", "repuesto_id": 99_999_999}]})
    assert r.status_code == 422
    assert "no existe" in r.json()["detail"]
    assert api.get(f"/presupuestos?orden_id={orden}", headers=MECANICO).json()["total"] == 0


@pytest.mark.parametrize("item", [
    {"tipo": "repuesto", "descripcion": "Sin repuesto", "cantidad": "1"},
    {"tipo": "mano_de_obra", "descripcion": "Con repuesto", "cantidad": "1", "repuesto_id": 1},
    {"tipo": "mano_de_obra", "descripcion": "Cantidad cero", "cantidad": "0"},
    {"tipo": "mano_de_obra", "descripcion": "Precio negativo", "cantidad": "1", "precio_unitario": "-1"},
    {"tipo": "pintura", "descripcion": "Tipo inválido", "cantidad": "1"},
    {"tipo": "mano_de_obra", "descripcion": "", "cantidad": "1"},
])
def test_items_invalidos_se_rechazan_con_422(api: TestClient, item: dict) -> None:
    r = api.post("/presupuestos", json={"orden_id": fabricas.nuevo_orden_id(), "items": [item]},
                 headers=MECANICO)
    assert r.status_code == 422


def test_campos_que_decide_el_servidor_se_rechazan(api: TestClient) -> None:
    r = api.post("/presupuestos", headers=MECANICO,
                 json={"orden_id": fabricas.nuevo_orden_id(), "creado_por_id": 99})
    assert r.status_code == 422


# --------------------------------------------------------------- consultas --

def test_listar_filtra_por_orden(api: TestClient, presupuesto_enviado: Presupuesto) -> None:
    r = api.get(f"/presupuestos?orden_id={presupuesto_enviado.orden_id}", headers=ADMIN)
    assert r.status_code == 200
    pagina = r.json()
    assert pagina["total"] == 1
    assert pagina["presupuestos"][0]["presupuesto_id"] == presupuesto_enviado.presupuesto_id
    assert pagina["presupuestos"][0]["estado_ultima_version"] == "enviada"


def test_listar_pagina_mas_recientes_primero(api: TestClient, db: Session) -> None:
    creados = [fabricas.nuevo_presupuesto(db).presupuesto_id for _ in range(3)]
    r = api.get("/presupuestos?desde=0&limite=2", headers=MECANICO)
    pagina = r.json()
    assert pagina["total"] >= 3 and len(pagina["presupuestos"]) == 2
    assert [p["presupuesto_id"] for p in pagina["presupuestos"]] == sorted(creados, reverse=True)[:2]
    assert api.get("/presupuestos?limite=0", headers=MECANICO).status_code == 422


def test_detalle_muestra_estado_de_cada_version(
    api: TestClient, presupuesto_aprobado: Presupuesto
) -> None:
    r = api.get(f"/presupuestos/{presupuesto_aprobado.presupuesto_id}", headers=ADMIN)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["version_vigente"] == 1
    v1 = cuerpo["versiones"][0]
    assert v1["estado"] == "aprobada" and v1["bloqueada_en"] is not None
    assert v1["decision"]["decision"] == "aprobado"


def test_detalle_de_version_rechazada_trae_motivo(
    api: TestClient, presupuesto_rechazado: Presupuesto
) -> None:
    r = api.get(f"/presupuestos/{presupuesto_rechazado.presupuesto_id}/versiones/1",
                headers=MECANICO)
    assert r.status_code == 200
    assert r.json()["estado"] == "rechazada" and r.json()["decision"]["motivo"]


@pytest.mark.parametrize("ruta", ["/presupuestos/987654321",
                                  "/presupuestos/987654321/versiones/1"])
def test_presupuesto_inexistente_es_404(api: TestClient, ruta: str) -> None:
    assert api.get(ruta, headers=ADMIN).status_code == 404


def test_version_inexistente_es_404(api: TestClient, presupuesto_borrador: Presupuesto) -> None:
    r = api.get(f"/presupuestos/{presupuesto_borrador.presupuesto_id}/versiones/9", headers=ADMIN)
    assert r.status_code == 404


# ------------------------------------------------------- editar el borrador --

def test_reemplazar_items_del_borrador(
    api: TestClient, presupuesto_borrador: Presupuesto, catalogo: dict[str, Repuesto]
) -> None:
    ruta = f"/presupuestos/{presupuesto_borrador.presupuesto_id}/versiones/1/items"
    r = api.put(ruta, json={"items": _items(catalogo)}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 2
    assert Decimal(r.json()["total"]) == datos.TOTAL_PRESUPUESTO_EJEMPLO
    # Vaciar también es válido mientras sea borrador.
    assert api.put(ruta, json={"items": []}, headers=ADMIN).json()["items"] == []


def test_version_enviada_no_se_edita_409(
    api: TestClient, db: Session, presupuesto_enviado: Presupuesto
) -> None:
    db.commit()  # confirma el dato de la fixture: el 409 revierte solo la petición
    antes = [(i.item_id, i.precio_unitario) for i in presupuesto_enviado.versiones[0].items]
    r = api.put(f"/presupuestos/{presupuesto_enviado.presupuesto_id}/versiones/1/items",
                json={"items": []}, headers=ADMIN)
    assert r.status_code == 409
    assert "ya fue enviada" in r.json()["detail"]
    db.expire_all()
    despues = [(i.item_id, i.precio_unitario)
               for i in db.get(Presupuesto, presupuesto_enviado.presupuesto_id).versiones[0].items]
    assert despues == antes


def test_version_aprobada_no_se_edita_409(
    api: TestClient, db: Session, presupuesto_aprobado: Presupuesto
) -> None:
    db.commit()
    r = api.put(f"/presupuestos/{presupuesto_aprobado.presupuesto_id}/versiones/1/items",
                json={"items": []}, headers=MECANICO)
    assert r.status_code == 409


# ------------------------------------------------------------------ acceso --

@pytest.mark.parametrize(("metodo", "ruta"), [
    ("post", "/presupuestos"), ("get", "/presupuestos"),
    ("get", "/presupuestos/1"), ("get", "/presupuestos/1/versiones/1"),
    ("put", "/presupuestos/1/versiones/1/items"),
])
def test_sin_token_401_y_cliente_403(api: TestClient, metodo: str, ruta: str) -> None:
    cuerpo = {"orden_id": 1, "items": []} if metodo != "get" else None
    assert api.request(metodo, ruta, json=cuerpo).status_code == 401
    assert api.request(metodo, ruta, json=cuerpo, headers=CLIENTE).status_code == 403
