"""Bloqueo de la versión aprobada y creación obligatoria de una nueva versión (SCRUM-528).

- La versión aprobada no se edita ni se borra: ni por la API (409 que indica
  cómo modificarla) ni directo en la base (triggers 0003_ms3).
- Modificar lo aprobado = POST /presupuestos/{id}/modificacion: crea la versión
  siguiente como copia editable de la APROBADA; la aprobada sigue vigente hasta
  que el cliente apruebe la modificación.
- La base exige (trigger 0009_ms3) que toda versión creada después de una
  aprobación sea una modificación, y que no haya dos borradores abiertos.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from services.ms3_presupuestos.models import ItemPresupuesto, Presupuesto, VersionPresupuesto
from services.ms3_presupuestos.tests import fabricas
from services.ms3_presupuestos.tests.test_operaciones_presupuesto import (  # noqa: F401
    ADMIN,
    CLIENTE,
    MECANICO,
    VerificadorFalso,
    _del_cliente,
    _ruta,
    api,
    ms2,
)

ITEM = {"tipo": "mano_de_obra", "descripcion": "Alineación", "cantidad": "1", "precio_unitario": "25000"}


def _modificar(api: TestClient, presupuesto: Presupuesto, cuerpo: dict | None = None, cabecera=MECANICO):
    return api.post(f"/presupuestos/{presupuesto.presupuesto_id}/modificacion", headers=cabecera,
                    json=cuerpo if cuerpo is not None else {})


def _versiones(api: TestClient, presupuesto: Presupuesto) -> list[dict]:
    return api.get(f"/presupuestos/{presupuesto.presupuesto_id}", headers=MECANICO).json()["versiones"]


def _item(descripcion: str, precio: str) -> ItemPresupuesto:
    return ItemPresupuesto(tipo="mano_de_obra", descripcion=descripcion, cantidad=Decimal("1"),
                           precio_unitario=Decimal(precio))


# ================================================== la versión aprobada ==

def test_editar_la_version_aprobada_es_409_y_explica_como_modificarla(
    api: TestClient, db: Session, presupuesto_aprobado: Presupuesto
) -> None:
    db.commit()  # el 409 hace rollback de la petición
    r = api.put(_ruta(presupuesto_aprobado, 1, "items"), headers=MECANICO, json={"items": [ITEM]})
    assert r.status_code == 409
    assert "aprobada y bloqueada" in r.json()["detail"]
    assert f"/presupuestos/{presupuesto_aprobado.presupuesto_id}/modificacion" in r.json()["detail"]


def test_la_version_aprobada_figura_bloqueada_y_vigente(
    api: TestClient, presupuesto_aprobado: Presupuesto
) -> None:
    v1 = _versiones(api, presupuesto_aprobado)[0]
    assert (v1["estado"], v1["vigente"]) == ("aprobada", True)
    assert v1["bloqueada_en"] is not None


@pytest.mark.parametrize("sql", [
    "update version_presupuesto set es_modificacion = true where version_id = :v",
    "delete from version_presupuesto where version_id = :v",
    "update item_presupuesto set precio_unitario = 1 where version_id = :v",
    "delete from item_presupuesto where version_id = :v",
])
def test_la_base_impide_tocar_la_version_aprobada(
    db: Session, presupuesto_aprobado: Presupuesto, sql: str
) -> None:
    v1 = presupuesto_aprobado.versiones[0]
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text(sql), {"v": v1.version_id})


# ========================================= modificar = nueva versión obligatoria ==

def test_modificar_crea_una_copia_editable_de_la_aprobada(
    api: TestClient, db: Session
) -> None:
    p = fabricas.nuevo_presupuesto(db, estado="aprobado", items=[_item("Cambio de aceite", "30000")])

    r = _modificar(api, p)

    assert r.status_code == 201, r.text
    v1, v2 = r.json()["versiones"]
    assert (v1["estado"], v1["vigente"]) == ("aprobada", True)
    assert (v2["numero"], v2["estado"], v2["es_modificacion"], v2["vigente"]) == (2, "borrador", True, False)
    assert [(i["descripcion"], i["precio_unitario"]) for i in v2["items"]] == [("Cambio de aceite", "30000.00")]
    assert r.json()["version_vigente"] == 1


def test_modificar_con_items_parte_de_esa_lista(api: TestClient, presupuesto_aprobado: Presupuesto) -> None:
    r = _modificar(api, presupuesto_aprobado, {"items": [ITEM]})
    assert r.status_code == 201
    assert [i["descripcion"] for i in r.json()["versiones"][-1]["items"]] == ["Alineación"]


def test_la_modificacion_se_edita_y_la_aprobada_no_cambia(
    api: TestClient, db: Session
) -> None:
    p = fabricas.nuevo_presupuesto(db, estado="aprobado", items=[_item("Frenos", "40000")])
    _modificar(api, p)
    r = api.put(_ruta(p, 2, "items"), headers=MECANICO, json={"items": [ITEM]})
    assert r.status_code == 200
    v1, v2 = _versiones(api, p)
    assert [i["descripcion"] for i in v1["items"]] == ["Frenos"]
    assert [i["descripcion"] for i in v2["items"]] == ["Alineación"]


def test_hasta_aprobar_la_modificacion_manda_la_aprobada(
    api: TestClient, db: Session, ms2: VerificadorFalso
) -> None:
    p = _del_cliente(ms2, fabricas.nuevo_presupuesto(db, estado="aprobado"))
    _modificar(api, p)
    assert api.post(_ruta(p, 2, "envio"), headers=ADMIN).status_code == 200
    assert _versiones(api, p)[0]["vigente"] is True

    r = api.post(_ruta(p, 2, "decision"), headers=CLIENTE, json={"decision": "aprobado"})
    assert r.status_code == 201, r.text
    v1, v2 = _versiones(api, p)
    assert (v1["estado"], v1["vigente"]) == ("aprobada", False)  # sigue bloqueada, ya no manda
    assert (v2["estado"], v2["vigente"]) == ("aprobada", True)
    assert v1["bloqueada_en"] is not None and v2["bloqueada_en"] is not None


def test_tras_rechazar_una_modificacion_se_parte_de_lo_aprobado(
    api: TestClient, db: Session
) -> None:
    p = fabricas.nuevo_presupuesto(db, estado="aprobado", items=[_item("Aprobado", "10000")])
    v2 = fabricas.nueva_version_siguiente(db, p, items=[_item("Propuesta rechazada", "99000")])
    fabricas.enviar(db, v2)
    fabricas.decidir(db, v2, "rechazado", "Muy caro")

    # Tanto la modificación como una nueva versión sin items copian lo APROBADO.
    r = _modificar(api, p)
    assert [i["descripcion"] for i in r.json()["versiones"][-1]["items"]] == ["Aprobado"]


def test_sin_version_aprobada_no_hay_modificacion(api: TestClient, presupuesto_enviado: Presupuesto) -> None:
    r = _modificar(api, presupuesto_enviado)
    assert r.status_code == 409 and "no tiene una versión aprobada" in r.json()["detail"]


def test_no_se_abre_una_segunda_modificacion(api: TestClient, presupuesto_aprobado: Presupuesto) -> None:
    assert _modificar(api, presupuesto_aprobado).status_code == 201
    r = _modificar(api, presupuesto_aprobado)
    assert r.status_code == 409 and "borrador" in r.json()["detail"]


def test_permisos_de_la_modificacion(api: TestClient, presupuesto_aprobado: Presupuesto) -> None:
    assert _modificar(api, presupuesto_aprobado, cabecera=CLIENTE).status_code == 403
    assert api.post(f"/presupuestos/{presupuesto_aprobado.presupuesto_id}/modificacion",
                    json={}).status_code == 401
    assert _modificar(api, presupuesto_aprobado, cabecera=ADMIN).status_code == 201
    assert api.post("/presupuestos/999999999/modificacion", headers=MECANICO, json={}).status_code == 404


# ============================================ la base lo exige (0009_ms3) ==

def _insertar_version(db: Session, p: Presupuesto, *, es_modificacion: bool) -> None:
    db.add(VersionPresupuesto(presupuesto_id=p.presupuesto_id, numero=p.siguiente_numero,
                              creado_por_id=2, es_modificacion=es_modificacion))
    db.flush()


def test_despues_de_aprobar_toda_version_nueva_es_modificacion(
    db: Session, presupuesto_aprobado: Presupuesto
) -> None:
    with pytest.raises(IntegrityError, match="debe registrarse como modificación"), db.begin_nested():
        _insertar_version(db, presupuesto_aprobado, es_modificacion=False)


def test_sin_aprobacion_una_version_no_es_modificacion(
    db: Session, presupuesto_enviado: Presupuesto
) -> None:
    with pytest.raises(IntegrityError, match="no es una modificación"), db.begin_nested():
        _insertar_version(db, presupuesto_enviado, es_modificacion=True)


def test_la_base_acepta_la_modificacion_correcta(db: Session, presupuesto_aprobado: Presupuesto) -> None:
    _insertar_version(db, presupuesto_aprobado, es_modificacion=True)
    db.refresh(presupuesto_aprobado)
    assert [v.es_modificacion for v in presupuesto_aprobado.versiones] == [False, True]
