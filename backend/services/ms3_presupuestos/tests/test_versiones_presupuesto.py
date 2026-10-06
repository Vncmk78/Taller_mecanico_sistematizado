"""Creación de versiones sin sobrescribir las anteriores (PostgreSQL).

Cada prueba toma una "foto" de las versiones previas (filas de
version_presupuesto, item_presupuesto y decision_presupuesto, leídas con SQL
directo) antes de crear la nueva versión y comprueba que sigue idéntica.
"""
from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.integracion_ms2 import obtener_verificador_ordenes
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import (
    ItemPresupuesto,
    Presupuesto,
    Repuesto,
    VersionPresupuesto,
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


class _OrdenesDelCliente:
    def __init__(self) -> None:
        self.propias: set[int] = set()

    def verificar_acceso(self, orden_id: int, token: str) -> None:
        from services.ms3_presupuestos.integracion_ms2 import OrdenNoVisible
        if orden_id not in self.propias:
            raise OrdenNoVisible(orden_id)


@pytest.fixture
def ms2() -> _OrdenesDelCliente:
    return _OrdenesDelCliente()


@pytest.fixture
def api(db: Session, ms2: _OrdenesDelCliente) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[obtener_verificador_ordenes] = lambda: ms2
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(obtener_verificador_ordenes, None)


def _foto(db: Session, presupuesto_id: int) -> list[tuple]:
    """Estado exacto en la base de todas las versiones, ítems y decisiones."""
    return [tuple(f) for f in db.execute(text("""
        select v.version_id, v.numero, v.creado_por_id, v.creado_en, v.enviado_en,
               v.bloqueada_en, v.es_modificacion,
               i.item_id, i.tipo, i.repuesto_id, i.descripcion, i.cantidad, i.precio_unitario,
               d.decision, d.motivo, d.fecha_hora
        from version_presupuesto v
        left join item_presupuesto i on i.version_id = v.version_id
        left join decision_presupuesto d on d.version_id = v.version_id
        where v.presupuesto_id = :p
        order by v.numero, i.item_id
    """), {"p": presupuesto_id})]


def _nueva(api: TestClient, presupuesto: Presupuesto, cuerpo: dict | None = None,
           cabecera: dict | None = None):
    return api.post(f"/presupuestos/{presupuesto.presupuesto_id}/versiones",
                    json=cuerpo, headers=cabecera or MECANICO)


# ------------------------------------------------------ corrección (pre-aprobación) --

def test_corregir_version_enviada_crea_la_2_y_no_toca_la_1(
    api: TestClient, db: Session, presupuesto_ejemplo: Presupuesto
) -> None:
    antes = _foto(db, presupuesto_ejemplo.presupuesto_id)

    r = _nueva(api, presupuesto_ejemplo)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert [v["numero"] for v in cuerpo["versiones"]] == [1, 2]
    v1, v2 = cuerpo["versiones"]
    assert v2["estado"] == "borrador" and v2["es_modificacion"] is False
    assert v2["creado_por_id"] == datos.MECANICO_ID
    # Copia de contenido, filas nuevas.
    assert [(i["tipo"], i["descripcion"], i["subtotal"]) for i in v2["items"]] == \
           [(i["tipo"], i["descripcion"], i["subtotal"]) for i in v1["items"]]
    assert not {i["item_id"] for i in v1["items"]} & {i["item_id"] for i in v2["items"]}

    db.expire_all()
    assert _foto(db, presupuesto_ejemplo.presupuesto_id)[: len(antes)] == antes


def test_la_nueva_version_reemplaza_a_la_enviada_sin_decidir(
    api: TestClient, db: Session, ms2: _OrdenesDelCliente, presupuesto_enviado: Presupuesto
) -> None:
    assert _nueva(api, presupuesto_enviado).status_code == 201
    ms2.propias.add(presupuesto_enviado.orden_id)
    r = api.post(f"/presupuestos/{presupuesto_enviado.presupuesto_id}/versiones/1/decision",
                 headers=CLIENTE, json={"decision": "aprobado"})
    assert r.status_code == 409 and "reemplazada por la versión 2" in r.json()["detail"]
    # Para el cliente la 2 aún no existe (borrador); la 1 sigue visible en el historial.
    detalle = api.get(f"/presupuestos/{presupuesto_enviado.presupuesto_id}", headers=CLIENTE).json()
    assert [v["numero"] for v in detalle["versiones"]] == [1]


def test_corregir_tras_un_rechazo_que_cancelo_el_servicio_es_409(
    api: TestClient, presupuesto_rechazado: Presupuesto
) -> None:
    r = _nueva(api, presupuesto_rechazado)
    assert r.status_code == 409 and "cancelado" in r.json()["detail"]


# --------------------------------------------------- modificación (post-aprobación) --

def test_modificacion_tras_aprobacion_conserva_la_vigente(
    api: TestClient, db: Session, presupuesto_aprobado: Presupuesto
) -> None:
    antes = _foto(db, presupuesto_aprobado.presupuesto_id)
    r = _nueva(api, presupuesto_aprobado, cabecera=ADMIN)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    v2 = cuerpo["versiones"][1]
    assert v2["es_modificacion"] is True and v2["estado"] == "borrador"
    assert cuerpo["version_vigente"] == 1          # manda la aprobada
    assert cuerpo["versiones"][0]["estado"] == "aprobada"
    db.expire_all()
    assert _foto(db, presupuesto_aprobado.presupuesto_id)[: len(antes)] == antes


def test_tras_rechazar_una_modificacion_se_puede_proponer_otra(
    api: TestClient, db: Session, presupuesto_aprobado: Presupuesto
) -> None:
    v2 = fabricas.nueva_version_siguiente(db, presupuesto_aprobado)
    fabricas.enviar(db, v2)
    fabricas.decidir(db, v2, "rechazado", "Muy caro")
    r = _nueva(api, presupuesto_aprobado)
    assert r.status_code == 201
    numeros = [(v["numero"], v["estado"], v["es_modificacion"]) for v in r.json()["versiones"]]
    assert numeros == [(1, "aprobada", False), (2, "rechazada", True), (3, "borrador", True)]
    assert r.json()["version_vigente"] == 1


def test_copiar_de_una_version_anterior(
    api: TestClient, db: Session, presupuesto_aprobado: Presupuesto
) -> None:
    """Tras rechazar la 2, la 3 puede partir del contenido aprobado (la 1)."""
    v2 = fabricas.nueva_version_siguiente(db, presupuesto_aprobado)
    fabricas.enviar(db, v2)
    fabricas.decidir(db, v2, "rechazado", "No")
    r = _nueva(api, presupuesto_aprobado, {"copiar_de": 1})
    assert r.status_code == 201
    v1, _, v3 = r.json()["versiones"]
    assert [i["descripcion"] for i in v3["items"]] == [i["descripcion"] for i in v1["items"]]


def test_nueva_version_con_items_propios(
    api: TestClient, presupuesto_aprobado: Presupuesto, catalogo: dict[str, Repuesto]
) -> None:
    disco = catalogo["Disco de freno delantero"]
    r = _nueva(api, presupuesto_aprobado, {"items": [
        {"tipo": "mano_de_obra", "descripcion": "Revisión", "cantidad": "1", "precio_unitario": "20000"},
        {"tipo": "repuesto", "repuesto_id": disco.repuesto_id, "descripcion": "Discos",
         "cantidad": "2", "precio_unitario": "45000"},
    ]})
    assert r.status_code == 201, r.text
    v2 = r.json()["versiones"][1]
    assert Decimal(v2["total"]) == Decimal("110000")
    assert v2["items"][1]["repuesto_nombre"] == disco.nombre


# ------------------------------------------------------------------- límites --

def test_solo_un_borrador_abierto(api: TestClient, presupuesto_borrador: Presupuesto) -> None:
    r = _nueva(api, presupuesto_borrador)
    assert r.status_code == 409 and "sigue en borrador" in r.json()["detail"]


def test_dos_veces_seguidas_la_segunda_es_409(
    api: TestClient, presupuesto_enviado: Presupuesto
) -> None:
    assert _nueva(api, presupuesto_enviado).status_code == 201
    assert _nueva(api, presupuesto_enviado).status_code == 409


def test_items_y_copiar_de_juntos_es_422(api: TestClient, presupuesto_enviado: Presupuesto) -> None:
    assert _nueva(api, presupuesto_enviado, {"items": [], "copiar_de": 1}).status_code == 422


def test_copiar_de_inexistente_es_404_y_no_crea_nada(
    api: TestClient, db: Session, presupuesto_enviado: Presupuesto
) -> None:
    db.commit()
    assert _nueva(api, presupuesto_enviado, {"copiar_de": 9}).status_code == 404
    db.expire_all()
    assert len(db.get(Presupuesto, presupuesto_enviado.presupuesto_id).versiones) == 1


def test_repuesto_inexistente_es_422_y_no_crea_nada(
    api: TestClient, db: Session, presupuesto_enviado: Presupuesto
) -> None:
    db.commit()
    r = _nueva(api, presupuesto_enviado, {"items": [
        {"tipo": "repuesto", "repuesto_id": 99_999_999, "descripcion": "X", "cantidad": "1"}]})
    assert r.status_code == 422
    db.expire_all()
    assert len(db.get(Presupuesto, presupuesto_enviado.presupuesto_id).versiones) == 1


def test_presupuesto_inexistente_es_404(api: TestClient) -> None:
    assert api.post("/presupuestos/987654321/versiones", headers=ADMIN).status_code == 404


def test_cliente_no_crea_versiones(api: TestClient, presupuesto_enviado: Presupuesto) -> None:
    assert _nueva(api, presupuesto_enviado, cabecera=CLIENTE).status_code == 403


def test_flujo_completo_corregir_enviar_y_aprobar_la_2(
    api: TestClient, db: Session, ms2: _OrdenesDelCliente, presupuesto_enviado: Presupuesto
) -> None:
    pid = presupuesto_enviado.presupuesto_id
    assert _nueva(api, presupuesto_enviado).status_code == 201
    r = api.put(f"/presupuestos/{pid}/versiones/2/items", headers=ADMIN, json={"items": [
        {"tipo": "mano_de_obra", "descripcion": "Corregido", "cantidad": "1",
         "precio_unitario": "18000"}]})
    assert r.status_code == 200
    assert api.post(f"/presupuestos/{pid}/versiones/2/envio", headers=ADMIN).status_code == 200
    ms2.propias.add(presupuesto_enviado.orden_id)
    r = api.post(f"/presupuestos/{pid}/versiones/2/decision", headers=CLIENTE,
                 json={"decision": "aprobado"})
    assert r.status_code == 201
    versiones = r.json()["presupuesto"]["versiones"]
    assert [(v["numero"], v["estado"]) for v in versiones] == [(1, "enviada"), (2, "aprobada")]
    assert r.json()["presupuesto"]["version_vigente"] == 2


# ------------------------------------------------- la base también lo impide --

def test_la_base_rechaza_saltarse_un_numero(db: Session, presupuesto_enviado: Presupuesto) -> None:
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(VersionPresupuesto(presupuesto_id=presupuesto_enviado.presupuesto_id,
                                  numero=5, creado_por_id=datos.MECANICO_ID))
        db.flush()


def test_la_base_rechaza_mover_un_item_a_otra_version(
    db: Session, presupuesto_borrador: Presupuesto
) -> None:
    v2 = fabricas.nueva_version(db)  # otro presupuesto, en borrador
    item: ItemPresupuesto = presupuesto_borrador.versiones[0].items[0]
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("update item_presupuesto set version_id = :v where item_id = :i"),
                   {"v": v2.version_id, "i": item.item_id})
