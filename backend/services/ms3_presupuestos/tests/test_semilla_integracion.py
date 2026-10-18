"""Datos semilla de integración de MS3 (datos_integracion.py + semilla_integracion.py).

Comprueban que la semilla:
- es un catálogo válido (nombres únicos, ningún movimiento imposible);
- carga proveedores, repuestos y existencias con las reglas de la API;
- deja el stock igual a la suma de sus movimientos y lo comprometido por orden;
- cubre los casos para los que existe (alertas, umbral justo, reservas,
  búsqueda con tildes, proveedor sin repuestos);
- es idempotente y respeta las órdenes que se le indiquen.

Corren dentro de la transacción de prueba: no dejan datos.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_integracion as integ
from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos import semilla_integracion as semilla
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

MECANICO = {"Authorization": "Bearer " + crear_token_acceso(
    usuario_id=datos.MECANICO_ID, roles=[NombreRol.MECANICO],
    clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256")}

# La base de pruebas puede tener otros repuestos; se verifican solo los de la semilla.
NOMBRES = tuple(integ.repuestos_integracion())
TOTAL_MOVIMIENTOS = sum(len(r.movimientos) for r in integ.repuestos_integracion().values())


@pytest.fixture
def cargada(db: Session) -> semilla.ResumenCarga:
    return semilla.cargar_integracion(db)


@pytest.fixture
def api(db: Session, cargada) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_verificar_sin_filtro_revisa_todos_los_repuestos(db: Session, cargada) -> None:
    proveedor = db.scalars(select(Proveedor).where(Proveedor.nombre == "Electro Auto Sur")).one()
    db.add(Repuesto(proveedor=proveedor, nombre="Cargado sin movimientos", stock=4))
    db.flush()
    problemas = semilla.verificar_existencias(db)
    assert "Cargado sin movimientos: stock 4 pero los movimientos suman 0" in problemas
    assert semilla.verificar_existencias(db, nombres=NOMBRES) == []


def _repuesto(db: Session, nombre: str) -> Repuesto:
    return db.scalars(select(Repuesto).where(Repuesto.nombre == nombre)).one()


# ============================================================ el catálogo ==

def test_el_catalogo_de_integracion_es_valido() -> None:
    assert integ.validar_catalogo() == []


def test_cubre_todos_los_casos_de_inventario() -> None:
    general = datos.UMBRAL_GENERAL
    repuestos = integ.repuestos_integracion().values()

    def efectivo(r):
        return r.umbral_particular if r.umbral_particular is not None else general

    assert any(r.stock_esperado == 0 for r in repuestos), "sin stock"
    assert any(r.umbral_particular is not None and r.stock_esperado < r.umbral_particular
               for r in repuestos), "bajo umbral particular"
    assert any(r.umbral_particular is None and r.stock_esperado < general
               for r in repuestos), "bajo umbral general"
    assert any(r.stock_esperado == efectivo(r) for r in repuestos), "justo en el umbral"
    assert any(r.comprometido_esperado() for r in repuestos), "unidades reservadas"
    tipos = {m.tipo for r in repuestos for m in r.movimientos}
    assert tipos == {"ingreso", "ajuste", "compromiso", "consumo", "liberacion"}
    assert any(not p.repuestos for p in integ.CATALOGO_INTEGRACION), "proveedor sin repuestos"


@pytest.mark.parametrize(("movimientos", "error"), [
    ((integ.MovimientoDato("ingreso", 1), integ.MovimientoDato("consumo", 2, "en_reparacion")),
     "consume más"),
    ((integ.MovimientoDato("ingreso", 1), integ.MovimientoDato("compromiso", 2, "recibida")),
     "reserva más"),
    ((integ.MovimientoDato("ingreso", 3), integ.MovimientoDato("liberacion", 1, "recibida")),
     "libera más"),
    ((integ.MovimientoDato("ajuste", -1),), "stock negativo"),
    ((integ.MovimientoDato("consumo", 1),), "mal formado"),
])
def test_validar_detecta_movimientos_imposibles(
    monkeypatch: pytest.MonkeyPatch, movimientos, error: str
) -> None:
    roto = integ.ProveedorIntegracion("Proveedor roto", "x", (
        integ.RepuestoIntegracion("Repuesto roto", movimientos),))
    monkeypatch.setattr(integ, "CATALOGO_INTEGRACION", (*integ.CATALOGO_INTEGRACION, roto))
    problemas = integ.validar_catalogo()
    assert any(error in p for p in problemas), problemas


def test_validar_detecta_nombres_repetidos_con_el_catalogo_minimo(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    copia = replace(integ.CATALOGO_INTEGRACION[0], nombre=datos.CATALOGO[0].nombre.upper())
    monkeypatch.setattr(integ, "CATALOGO_INTEGRACION", (copia, *integ.CATALOGO_INTEGRACION[1:]))
    assert "Hay nombres de proveedor repetidos" in integ.validar_catalogo()


def test_un_catalogo_invalido_no_se_carga(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    roto = integ.ProveedorIntegracion("Proveedor roto", "x", (
        integ.RepuestoIntegracion("Repuesto roto", (integ.MovimientoDato("ajuste", -5),)),))
    monkeypatch.setattr(integ, "CATALOGO_INTEGRACION", (roto,))
    with pytest.raises(ValueError, match="stock negativo"):
        semilla.cargar_integracion(db)
    assert db.scalar(select(func.count()).select_from(Proveedor)
                     .where(Proveedor.nombre == "Proveedor roto")) == 0


# ================================================================ la carga ==

def test_carga_proveedores_repuestos_y_existencias(db: Session, cargada) -> None:
    esperados = integ.repuestos_integracion()
    assert len(cargada.proveedores_creados) == len(integ.CATALOGO_INTEGRACION)
    assert set(cargada.repuestos_creados) == set(esperados)
    assert cargada.movimientos_aplicados == TOTAL_MOVIMIENTOS
    assert cargada.movimientos_repetidos == 0

    for prov in integ.CATALOGO_INTEGRACION:
        proveedor = db.scalars(select(Proveedor).where(Proveedor.nombre == prov.nombre)).one()
        assert proveedor.contacto == prov.contacto
        assert {r.nombre for r in proveedor.repuestos} == {r.nombre for r in prov.repuestos}

    for nombre, dato in esperados.items():
        r = _repuesto(db, nombre)
        assert (r.stock, r.umbral_particular) == (dato.stock_esperado, dato.umbral_particular)

    assert semilla.verificar_existencias(db, nombres=NOMBRES) == []
    assert semilla.diferencias_con_semilla(db) == []


def test_cada_movimiento_queda_con_su_clave_fija_y_quien_lo_registro(db: Session, cargada) -> None:
    r = _repuesto(db, "Amortiguador delantero")
    movs = db.scalars(select(MovimientoInventario).where(MovimientoInventario.repuesto_id == r.repuesto_id)
                      .order_by(MovimientoInventario.movimiento_id)).all()
    assert [(m.tipo, m.cantidad, m.orden_id) for m in movs] == [
        ("ingreso", 6, None), ("compromiso", 3, 2), ("liberacion", 1, 2)]
    assert [m.clave_operacion for m in movs] == [
        semilla.clave_movimiento(r.repuesto_id, n) for n in (1, 2, 3)]
    assert [m.registrado_por_id for m in movs] == [datos.ADMIN_ID, datos.MECANICO_ID, datos.MECANICO_ID]


def test_los_umbrales_particulares_quedan_en_el_historial(db: Session, cargada) -> None:
    for nombre, dato in integ.repuestos_integracion().items():
        r = _repuesto(db, nombre)
        cambios = db.scalars(select(HistorialUmbral)
                             .where(HistorialUmbral.repuesto_id == r.repuesto_id)).all()
        if dato.umbral_particular is None:
            assert cambios == []
        else:
            assert [(c.valor_anterior, c.valor_nuevo) for c in cambios] == [(None, dato.umbral_particular)]


def test_crea_el_umbral_general_si_no_hay_uno_vigente(db: Session) -> None:
    db.execute(text("delete from parametro_inventario"))
    resumen = semilla.cargar_integracion(db)
    assert resumen.umbral_general_creado
    vigente = db.scalars(select(ParametroInventario)
                         .where(ParametroInventario.vigente_hasta.is_(None))).one()
    assert vigente.umbral_general == datos.UMBRAL_GENERAL


def test_respeta_el_umbral_general_existente(db: Session) -> None:
    db.execute(text("delete from parametro_inventario"))
    db.add(ParametroInventario(umbral_general=9, actualizado_por_id=datos.ADMIN_ID))
    db.flush()
    assert semilla.cargar_integracion(db).umbral_general_creado is False
    assert db.scalar(select(func.count()).select_from(ParametroInventario)) == 1


def test_es_idempotente(db: Session, cargada) -> None:
    def conteos():
        return tuple(db.scalar(select(func.count()).select_from(m))
                     for m in (Proveedor, Repuesto, MovimientoInventario, HistorialUmbral))

    antes = conteos()
    otra = semilla.cargar_integracion(db)
    assert otra.proveedores_creados == [] and otra.repuestos_creados == []
    assert (otra.movimientos_aplicados, otra.movimientos_repetidos) == (0, TOTAL_MOVIMIENTOS)
    assert conteos() == antes
    assert semilla.diferencias_con_semilla(db) == []


def test_reconoce_nombres_existentes_sin_importar_mayusculas(db: Session) -> None:
    db.add(Proveedor(nombre="ELECTRO AUTO SUR", contacto="cargado a mano"))
    db.flush()
    resumen = semilla.cargar_integracion(db)
    assert "Electro Auto Sur" not in resumen.proveedores_creados
    assert db.scalar(select(func.count()).select_from(Proveedor)
                     .where(func.lower(Proveedor.nombre) == "electro auto sur")) == 1
    assert semilla.verificar_existencias(db, nombres=NOMBRES) == []


def test_completa_una_carga_que_quedo_a_medias(db: Session) -> None:
    # Simula una carga cortada: el repuesto existe pero sin sus movimientos.
    proveedor = Proveedor(nombre="Importadora Ñuble", contacto="x")
    db.add(proveedor)
    db.flush()
    db.add(Repuesto(proveedor=proveedor, nombre="Filtro de aire", stock=0))
    db.flush()
    semilla.cargar_integracion(db)
    assert _repuesto(db, "Filtro de aire").stock == 10
    assert semilla.verificar_existencias(db, nombres=NOMBRES) == []


def test_usa_las_ordenes_indicadas(db: Session) -> None:
    ordenes = {"en_reparacion": 501, "recibida": 502}
    semilla.cargar_integracion(db, ordenes=ordenes)
    ordenes_usadas = set(db.scalars(select(MovimientoInventario.orden_id).distinct()
                                    .where(MovimientoInventario.clave_operacion.like("semilla-int:%"),
                                           MovimientoInventario.orden_id.is_not(None))))
    assert ordenes_usadas == {501, 502}
    assert semilla.diferencias_con_semilla(db, ordenes=ordenes) == []
    assert semilla.diferencias_con_semilla(db) != []


# ============================================================ verificación ==

def test_verificar_detecta_stock_que_no_cuadra(db: Session, cargada) -> None:
    db.execute(text("update repuesto set stock = 99 where nombre = 'Bomba de agua'"))
    db.expire_all()
    problemas = semilla.verificar_existencias(db, nombres=NOMBRES)
    assert problemas == ["Bomba de agua: stock 99 pero los movimientos suman 4"]


def test_diferencias_detecta_uso_posterior(db: Session, cargada) -> None:
    r = _repuesto(db, "Batería 12V 60Ah")
    db.add(MovimientoInventario(clave_operacion="uso-real-bateria", repuesto_id=r.repuesto_id,
                                tipo="consumo", cantidad=1, orden_id=1,
                                registrado_por_id=datos.MECANICO_ID))
    r.stock -= 1
    db.flush()
    assert semilla.verificar_existencias(db, nombres=NOMBRES) == []
    assert semilla.diferencias_con_semilla(db) == ["Batería 12V 60Ah: stock 2, se esperaba 3"]


# ===================================================== a través de la API ==

def test_alertas_marcan_exactamente_los_casos_previstos(api: TestClient) -> None:
    alertas = api.get("/inventario/alertas", headers=MECANICO).json()["alertas"]
    nombres = {a["nombre"] for a in alertas}
    assert {"Líquido de frenos DOT4 (500 ml)", "Alternador reacondicionado",
            "Kit de embrague"} <= nombres
    # Justo en el umbral (5 = 5) no es alerta, ni lo que tiene stock holgado.
    assert not nombres & {"Bujía de iridio", "Aceite sintético 5W-30 (litro)", "Batería 12V 60Ah"}


def test_stock_muestra_lo_reservado_para_la_orden(api: TestClient, db: Session) -> None:
    r = _repuesto(db, "Amortiguador delantero")
    stock = api.get(f"/inventario/stock/{r.repuesto_id}", headers=MECANICO).json()
    assert (stock["stock"], stock["comprometido"], stock["disponible"]) == (6, 2, 4)
    assert stock["compromisos"] == [{"orden_id": 2, "comprometido": 2}]


def test_busquedas_con_tildes_y_proveedor_sin_repuestos(api: TestClient) -> None:
    bujias = api.get("/repuestos", params={"q": "bujia"}, headers=MECANICO).json()
    assert "Bujía de iridio" in [r["nombre"] for r in bujias["repuestos"]]
    nuble = api.get("/proveedores", params={"q": "nuble"}, headers=MECANICO).json()
    assert [p["nombre"] for p in nuble["proveedores"]] == ["Importadora Ñuble"]
    vacios = api.get("/proveedores", params={"con_repuestos": "false"}, headers=MECANICO).json()
    assert "Neumáticos Cautín" in [p["nombre"] for p in vacios["proveedores"]]


def test_el_proveedor_sin_repuestos_se_puede_eliminar(api: TestClient, db: Session) -> None:
    admin = {"Authorization": "Bearer " + crear_token_acceso(
        usuario_id=datos.ADMIN_ID, roles=[NombreRol.ADMINISTRADOR],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256")}
    pid = db.scalars(select(Proveedor.proveedor_id)
                     .where(Proveedor.nombre == "Neumáticos Cautín")).one()
    assert api.delete(f"/proveedores/{pid}", headers=admin).status_code == 204
