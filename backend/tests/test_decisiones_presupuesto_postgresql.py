"""Migraciones, coordinación e idempotencia con PostgreSQL real y commits.

Requiere SCRUM397438_MS2_TEST_URL y SCRUM397438_MS3_TEST_URL apuntando a bases
locales descartables llamadas verificar_*. Cada prueba crea sus propios esquemas,
los migra y elimina únicamente esos esquemas al terminar. No usa tablas públicas.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from services.ms2_taller.models import HistorialAsignacion, HistorialEstado, OrdenTrabajo
from services.ms2_taller.services import ordenes as servicio_ordenes
from services.ms3_presupuestos.models import DecisionPresupuesto, VersionPresupuesto
from shared.auth import NombreRol
from test_ordenes_api import _crear_vehiculo
from test_decisiones_presupuesto_integracion import (
    _aplicar, _decidir, _estado_y_historial, _headers, preparar_flujo,
    test_cliente_multirol_solo_decide_presupuesto_de_su_orden as comprobar_multirol,
    test_decision_coordina_estado_historial_actor_y_motivo as comprobar_rama,
    test_fallo_despues_del_flush_revierte_estado_e_historial_juntos as comprobar_rollback,
    test_fallo_ms2_conserva_decision_y_retry_aplica_una_sola_vez as comprobar_fallo,
    test_no_acepta_hechos_actor_ni_destino_del_body as comprobar_body,
    test_repetir_decision_aplicacion_y_retry_no_duplica_historial as comprobar_retry,
    test_retry_despues_de_otro_estado_devuelve_aplicacion_original as comprobar_estado_posterior,
    test_stock_del_reintento_no_cambia_la_rama_persistida as comprobar_stock,
    test_aprobacion_historica_sin_snapshot_no_inventa_stock as comprobar_historica,
    test_ms2_sin_confirmacion_de_propiedad_no_deja_decision_guardada as comprobar_ms2_anterior,
)


def _config(servicio, conexion):
    config = Config()
    config.set_main_option("script_location", f"services/{servicio}/alembic")
    config.attributes["connection"] = conexion
    return config


@pytest.fixture
def bases_pg():
    urls = [os.environ.get(f"SCRUM397438_MS{numero}_TEST_URL") for numero in (2, 3)]
    if not all(urls):
        pytest.skip("Se requieren dos PostgreSQL locales descartables para SCRUM-397/438")
    for url in urls:
        destino = make_url(url)
        assert destino.drivername == "postgresql+psycopg"
        assert destino.host in {"127.0.0.1", "localhost", "::1"}
        assert destino.database.startswith("verificar_"), "No usar bases compartidas"
    assert urls[0] != urls[1], "MS2 y MS3 deben conservar bases separadas"
    esquema = f"prueba_397438_{uuid.uuid4().hex}"
    administradores, bases = [], []
    try:
        for url, servicio in zip(urls, ("ms2_taller", "ms3_presupuestos")):
            admin = create_engine(url)
            with admin.begin() as conexion:
                conexion.execute(text(f'create schema "{esquema}"'))
                conexion.execute(text(f'set local search_path to "{esquema}"'))
                command.upgrade(_config(servicio, conexion), "head")
            administradores.append(admin)
            motor = create_engine(
                url, pool_size=10,
                connect_args={"options": f"-csearch_path={esquema}",
                              "application_name": f"{esquema}_{servicio}"},
            )
            bases.append((motor, sessionmaker(motor, expire_on_commit=False)))
        yield SimpleNamespace(ms2=bases[0], ms3=bases[1], esquema=esquema)
    finally:
        for motor, _ in bases:
            motor.dispose()
        for admin in administradores:
            with admin.begin() as conexion:
                conexion.execute(text(f'drop schema "{esquema}" cascade'))
            admin.dispose()


@pytest.fixture
def flujo_pg(bases_pg, monkeypatch):
    yield from preparar_flujo(monkeypatch, bases_pg.ms2, bases_pg.ms3)


@pytest.mark.parametrize("decision,stock,esperado,motivo", [
    ("rechazado", 10, 8, "No autorizo el servicio"),
    ("aprobado", 10, 5, None), ("aprobado", 1, 4, None),
])
def test_tres_ramas_con_migraciones_y_triggers_reales(flujo_pg, decision, stock, esperado, motivo):
    comprobar_rama(flujo_pg, decision, stock, esperado, motivo)
    with flujo_pg.db3() as db:
        version = db.scalar(select(VersionPresupuesto))
        assert (version.bloqueada_en is not None) == (decision == "aprobado")


def _ahora_postgresql(flujo):
    with flujo.db2() as db:
        return db.scalar(text("select clock_timestamp()"))


def test_historial_persiste_fecha_hora_con_zona_en_postgresql(flujo_pg):
    antes = _ahora_postgresql(flujo_pg)
    respuesta = _decidir(flujo_pg, "aprobado", stock=10)
    assert respuesta.status_code == 201, respuesta.text

    _, historial = _estado_y_historial(flujo_pg)
    assert len(historial) == 1
    fecha_hora = historial[0].fecha_hora
    assert fecha_hora is not None
    assert fecha_hora.tzinfo is not None
    assert fecha_hora.utcoffset() is not None
    assert antes <= fecha_hora <= _ahora_postgresql(flujo_pg)
    assert historial[0].orden_id == flujo_pg.orden_id


def test_asignacion_especifica_crea_historial_completo_y_patch_no_la_sustituye(flujo_pg):
    with flujo_pg.db2() as db:
        vehiculo_id = _crear_vehiculo(db, usuario_cliente=10).vehiculo_id
    admin = _headers(99, NombreRol.ADMINISTRADOR)
    creada = flujo_pg.ms2.post("/ordenes", json={"vehiculo_id": vehiculo_id}, headers=admin)
    assert creada.status_code == 201
    orden_id = creada.json()["orden_id"]
    rechazada = flujo_pg.ms2.patch(
        f"/ordenes/{orden_id}/estado", json={"estado_destino": 2}, headers=admin,
    )
    assert rechazada.status_code == 409
    with flujo_pg.db2() as db:
        assert db.get(OrdenTrabajo, orden_id).estado_codigo == 1
        assert len(list(db.scalars(select(HistorialEstado).where(
            HistorialEstado.orden_id == orden_id,
        )))) == 1  # Solo la creación, sin transición rechazada.
    antes = _ahora_postgresql(flujo_pg)
    asignada = flujo_pg.ms2.put(
        f"/ordenes/{orden_id}/mecanico", json={"mecanico_id": 50}, headers=admin,
    )
    assert asignada.status_code == 200
    with flujo_pg.db2() as db:
        orden = db.get(OrdenTrabajo, orden_id)
        assert orden.estado_codigo == 2 and orden.mecanico_actual_id == 50
        historial = db.scalar(select(HistorialEstado).where(
            HistorialEstado.orden_id == orden_id, HistorialEstado.estado_nuevo == 2,
        ))
        assert (historial.estado_anterior, historial.estado_nuevo) == (1, 2)
        assert historial.actor_usuario_id == 99 and historial.origen == "usuario"
        assert historial.observacion is None
        assert historial.fecha_hora.utcoffset() is not None
        assert antes <= historial.fecha_hora <= _ahora_postgresql(flujo_pg)
        asignacion = db.scalar(select(HistorialAsignacion).where(
            HistorialAsignacion.orden_id == orden_id,
        ))
        assert asignacion.administrador_id == 99 and asignacion.mecanico_nuevo_id == 50


@pytest.mark.parametrize("destino,stock", [(4, 1), (5, 10)])
@pytest.mark.parametrize("usuario,rol", [(99, NombreRol.ADMINISTRADOR), (50, NombreRol.MECANICO)])
def test_patch_no_aprueba_pero_decision_verificada_si_aplica_en_postgresql(
    flujo_pg, destino, stock, usuario, rol,
):
    with flujo_pg.db2() as db:
        db.get(OrdenTrabajo, flujo_pg.orden_id).mecanico_actual_id = 50
        db.commit()
    respuesta = flujo_pg.ms2.patch(
        f"/ordenes/{flujo_pg.orden_id}/estado", json={"estado_destino": destino},
        headers=_headers(usuario, rol),
    )
    assert respuesta.status_code == 409
    assert _estado_y_historial(flujo_pg) == (3, [])
    decision = _decidir(flujo_pg, "aprobado", stock)
    assert decision.status_code == 201
    estado, historial = _estado_y_historial(flujo_pg)
    assert estado == destino and len(historial) == 1
    assert historial[0].actor_usuario_id == 42
    assert historial[0].decision_presupuesto_id == decision.json()["decision_id"]


def _preparar_finalizacion(flujo):
    assert _decidir(flujo).status_code == 201
    assert flujo.ms2.put(
        f"/ordenes/{flujo.orden_id}/mecanico", json={"mecanico_id": 50},
        headers=_headers(99, NombreRol.ADMINISTRADOR),
    ).status_code == 200


def test_finalizacion_conservada_persiste_actor_jwt_y_campos_en_postgresql(flujo_pg):
    _preparar_finalizacion(flujo_pg)
    antes = _ahora_postgresql(flujo_pg)
    respuesta = flujo_pg.ms2.patch(
        f"/ordenes/{flujo_pg.orden_id}/estado",
        json={"estado_destino": 6, "observacion": "  Trabajo autorizado finalizado  "},
        headers=_headers(50, NombreRol.MECANICO),
    )
    assert respuesta.status_code == 200
    estado, historial = _estado_y_historial(flujo_pg)
    assert estado == 6 and len(historial) == 2
    registro = next(h for h in historial if h.estado_nuevo == 6)
    assert (registro.estado_anterior, registro.estado_nuevo) == (5, estado)
    assert registro.orden_id == flujo_pg.orden_id
    assert registro.actor_usuario_id == 50 and registro.origen == "usuario"
    assert registro.observacion == "Trabajo autorizado finalizado"
    assert registro.fecha_hora.utcoffset() is not None
    assert antes <= registro.fecha_hora <= _ahora_postgresql(flujo_pg)


def test_error_tras_flush_del_patch_revierte_estado_e_historial_en_postgresql(flujo_pg, monkeypatch):
    _preparar_finalizacion(flujo_pg)
    registrar = servicio_ordenes.registrar_historial_estado

    def fallar_despues_de_escribir(db, **datos):
        registrar(db, **datos)
        db.flush()  # Ejecuta las escrituras reales antes de provocar el error.
        raise SQLAlchemyError("Fallo de persistencia simulado")

    monkeypatch.setattr(servicio_ordenes, "registrar_historial_estado", fallar_despues_de_escribir)
    respuesta = flujo_pg.ms2.patch(
        f"/ordenes/{flujo_pg.orden_id}/estado", json={"estado_destino": 6},
        headers=_headers(50, NombreRol.MECANICO),
    )
    assert respuesta.status_code == 500
    estado, historial = _estado_y_historial(flujo_pg)
    assert estado == 5 and len(historial) == 1
    assert historial[0].estado_nuevo == 5 and historial[0].decision_presupuesto_id is not None


@pytest.mark.parametrize("fallo,historias_antes", [("antes", 0), ("verificacion", 0), ("despues", 1)])
def test_comunicacion_fallida_conserva_decision_y_retry(flujo_pg, fallo, historias_antes):
    comprobar_fallo(flujo_pg, fallo, historias_antes)


def test_fallo_despues_de_escribir_revierte_estado_e_historial(flujo_pg):
    comprobar_rollback(flujo_pg)


def test_repetir_decision_y_retry_no_duplica(flujo_pg):
    comprobar_retry(flujo_pg)


def test_retry_conserva_rama_original_de_stock(flujo_pg):
    comprobar_stock(flujo_pg)


def test_aprobacion_historica_no_inventa_disponibilidad(flujo_pg):
    comprobar_historica(flujo_pg)


@pytest.mark.parametrize("campo", ["actor_usuario_id", "cliente_usuario_id", "orden_id"])
def test_decision_ms3_no_admite_atribucion_o_orden_del_body(flujo_pg, campo):
    respuesta = flujo_pg.ms3.post(
        f"/presupuestos/{flujo_pg.presupuesto_id}/versiones/1/decision",
        json={"decision": "aprobado", campo: 88}, headers=_headers(),
    )
    assert respuesta.status_code == 422
    with flujo_pg.db3() as db:
        assert list(db.scalars(select(DecisionPresupuesto))) == []
    assert _estado_y_historial(flujo_pg) == (3, [])


def test_base_rechaza_disponibilidad_en_una_decision_de_rechazo(flujo_pg):
    with flujo_pg.db3() as db:
        with pytest.raises(IntegrityError) as error:
            db.add(DecisionPresupuesto(
                version=db.scalar(select(VersionPresupuesto)), cliente_usuario_id=42,
                decision="rechazado", motivo="No autorizo", repuestos_disponibles=True,
            ))
            db.flush()
        assert error.value.orig.diag.constraint_name == "ck_decision_presupuesto_stock_solo_aprobacion"
        db.rollback()
        assert list(db.scalars(select(DecisionPresupuesto))) == []


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalido"}])
def test_consulta_aplicacion_y_retry_exigen_jwt(flujo_pg, headers):
    assert _aplicar(flujo_pg, 1, headers=headers).status_code == 401
    assert flujo_pg.ms3.get("/presupuestos/decisiones/1", headers=headers).status_code == 401
    assert flujo_pg.ms3.post("/presupuestos/decisiones/1/aplicacion", headers=headers).status_code == 401
    assert _estado_y_historial(flujo_pg) == (3, [])


def test_retry_despues_de_avanzar_estado(flujo_pg):
    comprobar_estado_posterior(flujo_pg)


@pytest.mark.parametrize("usuario,esperado", [(42, 201), (88, 404)])
def test_multirol_no_permite_decidir_presupuesto_ajeno(flujo_pg, usuario, esperado):
    comprobar_multirol(flujo_pg, usuario, esperado)


def test_ms2_anterior_no_permite_guardar_decision(flujo_pg, monkeypatch):
    comprobar_ms2_anterior(flujo_pg, monkeypatch)


@pytest.mark.parametrize("extra", [
    {"estado_destino": 8}, {"actor_usuario_id": 99},
    {"repuestos_disponibles": True}, {"evento": "rechazo_primer_presupuesto"},
])
def test_body_no_admite_actor_o_hechos_falsificados(flujo_pg, extra):
    comprobar_body(flujo_pg, extra)


@pytest.mark.parametrize("decision", ["aprobado", "rechazado"])
def test_modificacion_preserva_comportamiento_previo(flujo_pg, decision):
    # Aquí el trigger real ya dejó la primera aprobación bloqueada.
    # La comprobación compartida vuelve a asignar ese campo solo en SQLite.
    resultado = _decidir(flujo_pg)
    assert resultado.status_code == 201
    with flujo_pg.db3() as db:
        version = VersionPresupuesto(
            presupuesto_id=flujo_pg.presupuesto_id, numero=2, creado_por_id=50,
            es_modificacion=True,
        )
        db.add(version)
        db.flush()
        version.enviado_en = db.scalar(text("select now()"))
        db.commit()
    respuesta = flujo_pg.ms3.post(
        f"/presupuestos/{flujo_pg.presupuesto_id}/versiones/2/decision",
        json={"decision": decision, "motivo": "Trabajo adicional"}, headers=_headers(),
    )
    assert respuesta.status_code == 201, respuesta.text
    decision_id = respuesta.json()["decision_id"]
    assert respuesta.json()["aplicacion_en_orden"] is None
    assert _aplicar(flujo_pg, decision_id).status_code == 409
    assert len(_estado_y_historial(flujo_pg)[1]) == 1


@pytest.mark.parametrize("body", [{}, {"observacion": None}, {"observacion": ""},
                                 {"observacion": " \t\n "}, {"observacion": "Motivo válido"}])
def test_cancelacion_exige_motivo_en_postgresql(flujo_pg, body):
    respuesta = flujo_pg.ms2.patch(
        f"/ordenes/{flujo_pg.orden_id}/estado", json={"estado_destino": 8, **body},
        headers=_headers(99, rol=NombreRol.ADMINISTRADOR),
    )
    valida = body.get("observacion") == "Motivo válido"
    assert respuesta.status_code == (200 if valida else 422)
    estado, historial = _estado_y_historial(flujo_pg)
    assert estado == (8 if valida else 3) and len(historial) == int(valida)


def test_decision_de_otra_orden_y_usuario_no_se_aplica(flujo_pg):
    flujo_pg.fallo["modo"] = "antes"
    decision_id = _decidir(flujo_pg).json()["decision_id"]
    flujo_pg.fallo["modo"] = None
    with flujo_pg.db2() as db:
        original = db.get(OrdenTrabajo, flujo_pg.orden_id)
        otra = OrdenTrabajo(vehiculo_id=original.vehiculo_id, ingreso_id=original.ingreso_id,
                            creado_por_id=99, estado_codigo=3)
        db.add(otra)
        db.commit()
        otra_id = otra.orden_id
    assert _aplicar(flujo_pg, decision_id, orden_id=otra_id).status_code == 404
    assert _aplicar(flujo_pg, decision_id, headers=_headers(88)).status_code == 404
    assert flujo_pg.ms3.get(f"/presupuestos/decisiones/{decision_id}", headers=_headers(88)).status_code == 404
    assert _estado_y_historial(flujo_pg) == (3, [])


@pytest.mark.parametrize("decision,stock,destino", [("rechazado", 10, 8), ("aprobado", 10, 5), ("aprobado", 1, 4)])
def test_aplicaciones_simultaneas_esperan_lock_y_crean_un_solo_historial(flujo_pg, decision, stock, destino):
    flujo_pg.fallo["modo"] = "antes"
    decision_id = _decidir(flujo_pg, decision, stock).json()["decision_id"]
    flujo_pg.fallo["modo"] = None
    resultados, errores = [], []
    preparados = threading.Barrier(5)

    def aplicar():
        try:
            preparados.wait(timeout=10)
            resultados.append(_aplicar(flujo_pg, decision_id))
        except Exception as exc:
            errores.append(exc)

    hilos = [threading.Thread(target=aplicar, daemon=True) for _ in range(4)]
    with flujo_pg.db2() as bloqueador:
        bloqueador.execute(text("select 1 from orden_trabajo where orden_id=:o for update"),
                            {"o": flujo_pg.orden_id})
        try:
            for hilo in hilos:
                hilo.start()
            preparados.wait(timeout=10)
            deadline = time.monotonic() + 10
            with flujo_pg.db2() as observador:
                aplicacion = observador.scalar(text("select current_setting('application_name')"))
                while time.monotonic() < deadline:
                    esperando = observador.scalar(text(
                        "select count(*) from pg_stat_activity "
                        "where application_name=:aplicacion and wait_event_type='Lock' "
                        "and cardinality(pg_blocking_pids(pid)) > 0"
                    ), {"aplicacion": aplicacion})
                    if esperando == 4:
                        break
                    observador.rollback()
                    threading.Event().wait(0.02)
            assert esperando == 4, "Las cuatro peticiones deben esperar el lock real de PostgreSQL"
            assert not resultados
        finally:
            bloqueador.rollback()
            for hilo in hilos:
                if hilo.ident is not None:
                    hilo.join(timeout=10)
    assert not errores and not any(hilo.is_alive() for hilo in hilos)
    assert len(resultados) == 4 and all(r.status_code == 200 for r in resultados)
    assert all(r.json() == resultados[0].json() for r in resultados)
    estado, historial = _estado_y_historial(flujo_pg)
    assert estado == destino and len(historial) == 1
    assert historial[0].decision_presupuesto_id == decision_id


def test_restricciones_indices_y_decision_inmutable(flujo_pg, bases_pg):
    inspector2 = inspect(bases_pg.ms2[0])
    columnas = {c["name"]: c for c in inspector2.get_columns("historial_estado")}
    assert columnas["decision_presupuesto_id"]["nullable"]
    unicas = {c["name"]: c for c in inspector2.get_unique_constraints("historial_estado")}
    assert unicas["uq_historial_estado_decision_presupuesto_id"]["column_names"] == ["decision_presupuesto_id"]
    assert "ix_historial_estado_orden_fecha" in {i["name"] for i in inspector2.get_indexes("historial_estado")}
    assert "ck_historial_estado_decision_presupuesto_positiva" in {c["name"] for c in inspector2.get_check_constraints("historial_estado")}
    assert not any("decision_presupuesto_id" in fk["constrained_columns"] for fk in inspector2.get_foreign_keys("historial_estado"))
    inspector3 = inspect(bases_pg.ms3[0])
    assert "ck_decision_presupuesto_stock_solo_aprobacion" in {c["name"] for c in inspector3.get_check_constraints("decision_presupuesto")}
    assert next(c for c in inspector3.get_columns("decision_presupuesto") if c["name"] == "repuestos_disponibles")["nullable"]
    decision_id = _decidir(flujo_pg).json()["decision_id"]
    with flujo_pg.db2() as db:
        for referencia in (decision_id, 0, -1):
            with pytest.raises(IntegrityError):
                db.add(HistorialEstado(orden_id=flujo_pg.orden_id, estado_anterior=3,
                                       estado_nuevo=5, actor_usuario_id=42, origen="usuario",
                                       decision_presupuesto_id=referencia))
                db.flush()
            db.rollback()
    with flujo_pg.db3() as db:
        with pytest.raises(IntegrityError):
            db.execute(text("update decision_presupuesto set repuestos_disponibles=false where decision_id=:d"),
                       {"d": decision_id})
        db.rollback()
        assert db.get(DecisionPresupuesto, decision_id).repuestos_disponibles is True
    assert len(_estado_y_historial(flujo_pg)[1]) == 1


def test_nuevas_migraciones_reversibles_en_esquemas_descartables(bases_pg):
    for (motor, _), servicio, anterior, columna, tabla in (
        (bases_pg.ms2, "ms2_taller", "0005_ms2", "decision_presupuesto_id", "historial_estado"),
        (bases_pg.ms3, "ms3_presupuestos", "0003_ms3", "repuestos_disponibles", "decision_presupuesto"),
    ):
        with motor.begin() as conexion:
            config = _config(servicio, conexion)
            command.downgrade(config, anterior)
            assert columna not in {c["name"] for c in inspect(conexion).get_columns(tabla)}
            command.upgrade(config, "head")
            assert columna in {c["name"] for c in inspect(conexion).get_columns(tabla)}
