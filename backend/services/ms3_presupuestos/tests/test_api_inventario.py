"""Inventario y stock (§4.6) contra PostgreSQL: movimientos, disponibilidad,
idempotencia, alertas, umbral general y concurrencia real.
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import (
    HistorialUmbral,
    ItemPresupuesto,
    MovimientoInventario,
    ParametroInventario,
    Repuesto,
)
from services.ms3_presupuestos.persistencia import ConflictoDeDatos, UnidadDeTrabajo
from services.ms3_presupuestos.schemas.inventario import MovimientoCrear
from services.ms3_presupuestos.services import inventario as casos
from services.ms3_presupuestos.services import presupuestos as casos_presupuestos
from services.ms3_presupuestos.tests import fabricas
from services.ms3_presupuestos.tests.test_rollback_consistencia import (  # noqa: F401
    esquema_aislado,
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
CLIENTE = _cabecera(NombreRol.CLIENTE, datos.CLIENTE_ID)


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


def _clave() -> str:
    return f"prueba-{uuid.uuid4().hex}"


def _mover(api: TestClient, repuesto: Repuesto | int, tipo: str, cantidad: int,
           orden_id: int | None = None, *, cabecera: dict | None = None, clave: str | None = None):
    rid = repuesto if isinstance(repuesto, int) else repuesto.repuesto_id
    cuerpo = {"clave_operacion": clave or _clave(), "repuesto_id": rid, "tipo": tipo,
              "cantidad": cantidad}
    if orden_id is not None:
        cuerpo["orden_id"] = orden_id
    return api.post("/inventario/movimientos", json=cuerpo,
                    headers=cabecera or (ADMIN if tipo in ("ingreso", "ajuste") else MECANICO))


def _stock(api: TestClient, repuesto: Repuesto) -> dict:
    r = api.get(f"/inventario/stock/{repuesto.repuesto_id}", headers=MECANICO)
    assert r.status_code == 200, r.text
    return r.json()


# ============================================================ ingreso / ajuste ==

def test_ingreso_suma_stock_y_queda_registrado(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=2)
    r = _mover(api, repuesto, "ingreso", 5)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["stock"]["stock"] == 7 and cuerpo["repetido"] is False
    mov = cuerpo["movimiento"]
    assert (mov["tipo"], mov["cantidad"], mov["registrado_por_id"]) == ("ingreso", 5, datos.ADMIN_ID)
    db.expire_all()
    assert db.get(Repuesto, repuesto.repuesto_id).stock == 7


def test_ajuste_puede_restar_pero_no_dejar_stock_negativo(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=3)
    assert _mover(api, repuesto, "ajuste", -2).json()["stock"]["stock"] == 1
    r = _mover(api, repuesto, "ajuste", -2)
    assert r.status_code == 409 and "dejaría el stock" in r.json()["detail"]
    assert _stock(api, repuesto)["stock"] == 1


@pytest.mark.parametrize("tipo", ["ingreso", "ajuste"])
def test_solo_el_administrador_ingresa_o_ajusta(api: TestClient, db: Session, tipo: str) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=3)
    assert _mover(api, repuesto, tipo, 1, cabecera=MECANICO).status_code == 403
    assert _mover(api, repuesto, tipo, 1, cabecera=CLIENTE).status_code == 403


# =============================================== compromiso / consumo / liberación ==

def test_compromiso_reserva_sin_tocar_el_stock_fisico(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=5)
    orden = fabricas.nuevo_orden_id()
    r = _mover(api, repuesto, "compromiso", 3, orden)
    assert r.status_code == 201, r.text
    estado = r.json()["stock"]
    assert (estado["stock"], estado["comprometido"], estado["disponible"]) == (5, 3, 2)
    assert estado["compromisos"] == [{"orden_id": orden, "comprometido": 3}]


def test_no_se_ofrecen_las_mismas_unidades_a_dos_ordenes(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=5)
    orden_a, orden_b = fabricas.nuevo_orden_id(), fabricas.nuevo_orden_id()
    assert _mover(api, repuesto, "compromiso", 4, orden_a).status_code == 201
    r = _mover(api, repuesto, "compromiso", 2, orden_b)
    assert r.status_code == 409 and "disponibles 1" in r.json()["detail"]
    assert _mover(api, repuesto, "compromiso", 1, orden_b).status_code == 201
    assert _stock(api, repuesto)["disponible"] == 0


def test_consumo_descuenta_y_usa_primero_lo_reservado(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=6)
    orden = fabricas.nuevo_orden_id()
    _mover(api, repuesto, "compromiso", 2, orden)
    r = _mover(api, repuesto, "consumo", 3, orden)   # 2 reservadas + 1 libre
    assert r.status_code == 201, r.text
    estado = r.json()["stock"]
    assert (estado["stock"], estado["comprometido"], estado["disponible"]) == (3, 0, 3)


def test_consumo_no_toma_unidades_reservadas_por_otra_orden(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=4)
    otra, mia = fabricas.nuevo_orden_id(), fabricas.nuevo_orden_id()
    _mover(api, repuesto, "compromiso", 3, otra)
    r = _mover(api, repuesto, "consumo", 2, mia)
    assert r.status_code == 409 and "Stock insuficiente" in r.json()["detail"]
    assert _mover(api, repuesto, "consumo", 1, mia).status_code == 201
    estado = _stock(api, repuesto)
    assert (estado["stock"], estado["comprometido"]) == (3, 3)


def test_liberacion_devuelve_disponibilidad_y_no_excede_lo_reservado(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=5)
    orden = fabricas.nuevo_orden_id()
    _mover(api, repuesto, "compromiso", 3, orden)
    r = _mover(api, repuesto, "liberacion", 4, orden)
    assert r.status_code == 409 and "tiene 3" in r.json()["detail"]
    estado = _mover(api, repuesto, "liberacion", 3, orden).json()["stock"]
    assert (estado["stock"], estado["comprometido"], estado["disponible"]) == (5, 0, 5)
    assert _mover(api, repuesto, "liberacion", 1, fabricas.nuevo_orden_id()).status_code == 409


@pytest.mark.parametrize("cuerpo", [
    {"tipo": "compromiso", "cantidad": 1},                    # sin orden
    {"tipo": "ingreso", "cantidad": 1, "orden_id": 5},        # ingreso con orden
    {"tipo": "consumo", "cantidad": 0, "orden_id": 5},
    {"tipo": "consumo", "cantidad": -1, "orden_id": 5},
    {"tipo": "ajuste", "cantidad": 0},
    {"tipo": "regalo", "cantidad": 1},
])
def test_movimientos_invalidos_son_422(api: TestClient, db: Session, cuerpo: dict) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=5)
    r = api.post("/inventario/movimientos", headers=ADMIN,
                 json={"clave_operacion": _clave(), "repuesto_id": repuesto.repuesto_id, **cuerpo})
    assert r.status_code == 422


def test_repuesto_inexistente_es_404(api: TestClient) -> None:
    assert _mover(api, 987654321, "ingreso", 1).status_code == 404
    assert api.get("/inventario/stock/987654321", headers=ADMIN).status_code == 404


# ============================================================== idempotencia ==

def test_la_misma_clave_no_descuenta_dos_veces(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=5)
    orden, clave = fabricas.nuevo_orden_id(), _clave()
    primera = _mover(api, repuesto, "consumo", 2, orden, clave=clave)
    segunda = _mover(api, repuesto, "consumo", 2, orden, clave=clave)
    assert primera.status_code == 201 and segunda.status_code == 200
    assert segunda.json()["repetido"] is True
    assert segunda.json()["movimiento"]["movimiento_id"] == primera.json()["movimiento"]["movimiento_id"]
    assert _stock(api, repuesto)["stock"] == 3
    assert len(db.scalars(select(MovimientoInventario)
                          .where(MovimientoInventario.clave_operacion == clave)).all()) == 1


def test_clave_reutilizada_con_otros_datos_es_409(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=5)
    clave = _clave()
    _mover(api, repuesto, "ingreso", 2, clave=clave)
    r = _mover(api, repuesto, "ingreso", 3, clave=clave)
    assert r.status_code == 409 and "ya se usó" in r.json()["detail"]
    assert _stock(api, repuesto)["stock"] == 7


# ================================================================== alertas ==

def test_alerta_se_activa_una_vez_y_se_apaga_al_reponer(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=6, umbral_particular=5)
    orden = fabricas.nuevo_orden_id()
    r = _mover(api, repuesto, "consumo", 1, orden)       # 5: igual al umbral, NO es alerta
    assert r.json()["alerta"] == {"activa": False, "nueva": False}
    r = _mover(api, repuesto, "consumo", 1, orden)       # 4 < 5: se activa
    assert r.json()["alerta"] == {"activa": True, "nueva": True}
    r = _mover(api, repuesto, "consumo", 1, orden)       # sigue bajo: no se repite el aviso
    assert r.json()["alerta"] == {"activa": True, "nueva": False}
    r = _mover(api, repuesto, "ingreso", 10)
    assert r.json()["alerta"] == {"activa": False, "nueva": False}


def test_listado_de_alertas_usa_umbral_particular_o_general(api: TestClient, db: Session) -> None:
    fabricas.umbral_general_vigente(db, valor=4)
    proveedor = fabricas.nuevo_proveedor(db, repuestos=())
    bajo_general = fabricas.nuevo_repuesto(db, stock=1, proveedor=proveedor)                    # faltan 3
    bajo_particular = fabricas.nuevo_repuesto(db, stock=5, umbral_particular=6, proveedor=proveedor)  # 1
    fabricas.nuevo_repuesto(db, stock=4, proveedor=proveedor)                                   # =4: no
    cuerpo = api.get("/inventario/alertas", headers=MECANICO).json()
    assert cuerpo["umbral_general"] == 4
    ids = [a["repuesto_id"] for a in cuerpo["alertas"]]
    assert bajo_general.repuesto_id in ids and bajo_particular.repuesto_id in ids
    assert ids.index(bajo_general.repuesto_id) < ids.index(bajo_particular.repuesto_id)
    alerta = next(a for a in cuerpo["alertas"] if a["repuesto_id"] == bajo_general.repuesto_id)
    assert (alerta["stock"], alerta["umbral_efectivo"], alerta["faltan"]) == (1, 4, 3)


# ============================================================ umbral general ==

def test_cambiar_umbral_general_cierra_el_anterior_y_deja_historial(api: TestClient, db: Session) -> None:
    fabricas.umbral_general_vigente(db, valor=5)
    r = api.put("/inventario/umbral-general", headers=ADMIN,
                json={"umbral_general": 8, "observacion": "Temporada alta"})
    assert r.status_code == 200, r.text
    assert r.json()["umbral_general"] == 8 and r.json()["actualizado_por_id"] == datos.ADMIN_ID
    assert api.get("/inventario/umbral-general", headers=MECANICO).json()["umbral_general"] == 8

    vigentes = db.scalars(select(ParametroInventario)
                          .where(ParametroInventario.vigente_hasta.is_(None))).all()
    assert [v.umbral_general for v in vigentes] == [8]
    ultimo = api.get("/inventario/historial-umbral?solo_general=true&limite=1", headers=ADMIN).json()[0]
    assert (ultimo["valor_anterior"], ultimo["valor_nuevo"], ultimo["observacion"]) == (5, 8, "Temporada alta")


def test_mismo_umbral_general_no_genera_cambios(api: TestClient, db: Session) -> None:
    fabricas.umbral_general_vigente(db, valor=6)
    antes = db.scalar(select(text("count(*)")).select_from(HistorialUmbral))
    assert api.put("/inventario/umbral-general", headers=ADMIN,
                   json={"umbral_general": 6}).status_code == 200
    assert db.scalar(select(text("count(*)")).select_from(HistorialUmbral)) == antes


def test_umbral_general_solo_administrador_y_no_negativo(api: TestClient) -> None:
    assert api.put("/inventario/umbral-general", headers=MECANICO,
                   json={"umbral_general": 3}).status_code == 403
    assert api.put("/inventario/umbral-general", headers=ADMIN,
                   json={"umbral_general": -1}).status_code == 422


def test_historial_de_un_repuesto(api: TestClient) -> None:
    proveedor = api.post("/proveedores", headers=ADMIN,
                         json={"nombre": f"Prov {uuid.uuid4().hex[:6]}", "contacto": "x"}).json()
    rep = api.post("/repuestos", headers=ADMIN, json={
        "proveedor_id": proveedor["proveedor_id"], "nombre": "Correa", "umbral_particular": 2}).json()
    api.patch(f"/repuestos/{rep['repuesto_id']}", headers=ADMIN, json={"umbral_particular": 4})
    cambios = api.get(f"/inventario/historial-umbral?repuesto_id={rep['repuesto_id']}",
                      headers=MECANICO).json()
    assert [(c["valor_anterior"], c["valor_nuevo"]) for c in cambios] == [(2, 4), (None, 2)]
    assert api.get("/inventario/historial-umbral?repuesto_id=987654321",
                   headers=ADMIN).status_code == 404


# ======================================================== consultas y acceso ==

def test_movimientos_se_filtran_por_orden_y_tipo(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=10)
    orden = fabricas.nuevo_orden_id()
    _mover(api, repuesto, "compromiso", 2, orden)
    _mover(api, repuesto, "consumo", 1, orden)
    _mover(api, repuesto, "ingreso", 4)
    de_orden = api.get(f"/inventario/movimientos?orden_id={orden}", headers=MECANICO).json()
    assert de_orden["total"] == 2
    assert sorted(m["tipo"] for m in de_orden["movimientos"]) == ["compromiso", "consumo"]
    ingresos = api.get(f"/inventario/movimientos?repuesto_id={repuesto.repuesto_id}&tipo=ingreso",
                       headers=MECANICO).json()
    assert [m["cantidad"] for m in ingresos["movimientos"]] == [4]


@pytest.mark.parametrize("ruta", ["/inventario/movimientos", "/inventario/alertas",
                                  "/inventario/umbral-general", "/inventario/historial-umbral",
                                  "/inventario/stock/1"])
def test_el_cliente_no_accede_al_inventario(api: TestClient, ruta: str) -> None:
    assert api.get(ruta, headers=CLIENTE).status_code == 403
    assert api.get(ruta).status_code == 401


# ================================== integración con la aprobación de presupuestos ==

def test_aprobacion_considera_lo_comprometido_por_otras_ordenes(api: TestClient, db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=4)
    otra_orden = fabricas.nuevo_orden_id()
    _mover(api, repuesto, "compromiso", 2, otra_orden)                 # otra orden reserva 2
    version = fabricas.nueva_version(db, items=[ItemPresupuesto(
        tipo="repuesto", repuesto=repuesto, descripcion="x", cantidad=Decimal("3"),
        precio_unitario=Decimal("1000"))])
    faltantes = casos_presupuestos._repuestos_faltantes(UnidadDeTrabajo(db), version)
    assert [(f.repuesto_id, f.disponible) for f in faltantes] == [(repuesto.repuesto_id, 2)]

    # Si la otra orden libera, alcanza.
    _mover(api, repuesto, "liberacion", 2, otra_orden)
    assert casos_presupuestos._repuestos_faltantes(UnidadDeTrabajo(db), version) == []

    # Las reservas de la PROPIA orden sí cuentan como disponibles para ella.
    propia = version.presupuesto.orden_id
    _mover(api, repuesto, "compromiso", 3, propia)
    assert casos_presupuestos._repuestos_faltantes(UnidadDeTrabajo(db), version) == []


# ================================================= concurrencia real (§4.6) ==

def _repuesto_real(fabrica: sessionmaker[Session], stock: int) -> int:
    with fabrica() as sesion:
        repuesto = fabricas.nuevo_repuesto(sesion, stock=stock)
        sesion.commit()
        return repuesto.repuesto_id


def _a_la_vez(fabrica: sessionmaker[Session], repuesto_id: int,
              operaciones: list[Callable[[UnidadDeTrabajo], Any]]) -> list[Any]:
    """Todas esperan en el mismo FOR UPDATE del repuesto y compiten al liberarse."""
    resultados: list[Any] = [None] * len(operaciones)
    listas = threading.Barrier(len(operaciones) + 1)

    def correr(i: int, operacion: Callable[[UnidadDeTrabajo], Any]) -> None:
        with fabrica() as sesion:
            listas.wait()
            try:
                resultados[i] = operacion(UnidadDeTrabajo(sesion))
            except Exception as exc:  # noqa: BLE001
                resultados[i] = exc

    with fabrica() as bloqueador:
        bloqueador.execute(text("select 1 from repuesto where repuesto_id = :r for update"),
                           {"r": repuesto_id})
        hilos = [threading.Thread(target=correr, args=(i, op)) for i, op in enumerate(operaciones)]
        for hilo in hilos:
            hilo.start()
        listas.wait()
        threading.Event().wait(0.3)
        bloqueador.rollback()
        for hilo in hilos:
            hilo.join(timeout=20)
    return resultados


def _operacion(rid: int, tipo: str, cantidad: int, orden_id: int | None, clave: str | None = None):
    datos_mov = MovimientoCrear(clave_operacion=clave or _clave(), repuesto_id=rid, tipo=tipo,
                                cantidad=cantidad, orden_id=orden_id)
    return lambda uow: casos.registrar_movimiento(uow, datos_mov, usuario_id=datos.MECANICO_ID)


def test_dos_consumos_simultaneos_nunca_dejan_stock_negativo(esquema_aislado) -> None:  # noqa: F811
    rid = _repuesto_real(esquema_aislado, stock=4)
    resultados = _a_la_vez(esquema_aislado, rid, [
        _operacion(rid, "consumo", 3, fabricas.nuevo_orden_id()),
        _operacion(rid, "consumo", 3, fabricas.nuevo_orden_id()),
    ])
    exitos = [r for r in resultados if not isinstance(r, Exception)]
    errores = [r for r in resultados if isinstance(r, Exception)]
    assert len(exitos) == 1 and len(errores) == 1 and isinstance(errores[0], ConflictoDeDatos)
    with esquema_aislado() as sesion:
        assert sesion.get(Repuesto, rid).stock == 1


def test_compromisos_simultaneos_no_sobrevenden(esquema_aislado) -> None:  # noqa: F811
    rid = _repuesto_real(esquema_aislado, stock=5)
    resultados = _a_la_vez(esquema_aislado, rid, [
        _operacion(rid, "compromiso", 2, fabricas.nuevo_orden_id()) for _ in range(4)])
    assert sum(not isinstance(r, Exception) for r in resultados) == 2
    with esquema_aislado() as sesion:
        uow = UnidadDeTrabajo(sesion)
        assert sum(uow.movimientos.comprometido_por_orden(rid).values()) == 4
        assert sesion.get(Repuesto, rid).stock == 5


def test_la_misma_clave_en_paralelo_se_aplica_una_vez(esquema_aislado) -> None:  # noqa: F811
    rid = _repuesto_real(esquema_aislado, stock=10)
    orden, clave = fabricas.nuevo_orden_id(), _clave()
    resultados = _a_la_vez(esquema_aislado, rid, [
        _operacion(rid, "consumo", 2, orden, clave) for _ in range(3)])
    assert all(not isinstance(r, Exception) for r in resultados), resultados
    assert sorted(r.repetido for r in resultados) == [False, True, True]
    with esquema_aislado() as sesion:
        assert sesion.get(Repuesto, rid).stock == 8
