"""Aislamiento de la base REAL de MS3 (PostgreSQL migrado).

Comprueba en la base a la que se conecta MS3 que solo hay tablas de MS3, que
ninguna FK sale del servicio, que no hay dblink/postgres_fdw y que las
referencias lógicas aceptan ids que no existen en esta base (se validan por API).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from services.ms3_presupuestos import aislamiento
from services.ms3_presupuestos.db import Base
from services.ms3_presupuestos.models import MovimientoInventario, Presupuesto
from services.ms3_presupuestos.tests.fabricas import nuevo_repuesto


def test_base_de_ms3_esta_aislada(engine: Engine) -> None:
    with engine.connect() as conexion:
        assert aislamiento.problemas_en_base(conexion, Base.metadata) == []


def test_base_no_contiene_tablas_de_otros_servicios(db: Session) -> None:
    ajenas = {"usuario", "rol", "usuario_rol", "cliente", "vehiculo", "orden_trabajo",
              "estado_orden", "ingreso_vehiculo", "evidencia"}
    presentes = set(db.execute(text(
        "select table_name from information_schema.tables "
        "where table_schema = current_schema()")).scalars())
    assert not presentes & ajenas


def test_ids_de_otros_servicios_no_se_validan_en_esta_base(db: Session) -> None:
    """Sin FK física: la base acepta una orden/usuario que aquí no existe."""
    orden_inexistente, usuario_inexistente = 987_654_321, 876_543_210
    db.add(Presupuesto(orden_id=orden_inexistente))
    db.add(MovimientoInventario(
        clave_operacion="aislamiento-1", repuesto=nuevo_repuesto(db),
        orden_id=orden_inexistente, tipo="compromiso", cantidad=1,
        registrado_por_id=usuario_inexistente))
    db.flush()


def test_la_verificacion_detecta_una_tabla_ajena(db: Session) -> None:
    db.execute(text("create table orden_trabajo (orden_id int primary key)"))
    problemas = aislamiento.problemas_en_base(db.connection(), Base.metadata)
    assert any("orden_trabajo" in p for p in problemas)


def test_la_verificacion_detecta_una_fk_hacia_fuera(db: Session) -> None:
    db.execute(text("create table usuario (usuario_id int primary key)"))
    db.execute(text(
        "alter table parametro_inventario add constraint fk_prueba_usuario "
        "foreign key (actualizado_por_id) references usuario (usuario_id) not valid"))
    problemas = aislamiento.problemas_en_base(db.connection(), Base.metadata)
    assert any("fk_prueba_usuario" in p for p in problemas)
