"""Control transaccional del registro de órdenes (SQLite).

`registrar_orden_sin_confirmar` es el núcleo que crea ingreso, orden, historial
y evento de outbox sin confirmar; `crear_orden` (POST /ordenes) lo confirma o lo
deshace por completo. Un rechazo de cupo deshace todo y guarda después, en una
transacción propia, la auditoría con los datos de la validación original.

La concurrencia real del cupo se verifica en `test_registro_orden_postgresql.py`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import services.ms2_taller.services.cupo_ingresos as servicio_cupo
from services.ms2_taller.models import (
    ConfiguracionCupoIngresos,
    EventoOutbox,
    HistorialEstado,
    IngresoVehiculo,
    OrdenTrabajo,
    Vehiculo,
)
from services.ms2_taller.models.configuracion_cupo_ingresos import (
    HistorialValidacionCupoIngreso,
)
from services.ms2_taller.services.cupo_ingresos import (
    CupoDiarioExcedidoError,
    CupoDiarioNoConfiguradoError,
)
from services.ms2_taller.services.ordenes import (
    PersistenciaOrdenError,
    crear_orden,
    registrar_orden_sin_confirmar,
)
from shared.auth import NombreRol
from test_ordenes_api import (  # noqa: F401  (fixtures)
    _crear_vehiculo,
    _headers_para,
    api_ordenes,
    db_ordenes,
)

ADMIN = 99


def _conteos(db: Session) -> dict[str, int]:
    db.expire_all()
    modelos = {
        "ingresos": IngresoVehiculo,
        "ordenes": OrdenTrabajo,
        "historial": HistorialEstado,
        "outbox": EventoOutbox,
        "validaciones": HistorialValidacionCupoIngreso,
    }
    return {
        nombre: db.scalar(select(func.count()).select_from(modelo))
        for nombre, modelo in modelos.items()
    }


def _fijar_cupo(db: Session, maximo: int | None) -> None:
    db.get(ConfiguracionCupoIngresos, 1).max_ingresos_diarios = maximo
    db.commit()


def _post(api: TestClient, vehiculo: Vehiculo):
    return api.post(
        "/ordenes",
        json={"vehiculo_id": vehiculo.vehiculo_id},
        headers=_headers_para(ADMIN, NombreRol.ADMINISTRADOR),
    )


# ── núcleo sin confirmar ───────────────────────────────────────────────────


def test_el_nucleo_registra_todo_pero_no_confirma(db_ordenes: Session):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    antes = _conteos(db_ordenes)

    orden = registrar_orden_sin_confirmar(db_ordenes, vehiculo.vehiculo_id, ADMIN)

    # Dentro de la transacción están ingreso, orden, historial, evento y validación.
    assert orden.orden_id is not None and orden.estado_codigo == 1
    assert db_ordenes.in_transaction()
    db_ordenes.rollback()
    assert _conteos(db_ordenes) == antes


def test_un_rechazo_en_el_nucleo_no_confirma_cambios_previos_del_llamador(
    db_ordenes: Session,
):
    """Antes la validación hacía commit y arrastraba lo pendiente del llamador."""

    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    _fijar_cupo(db_ordenes, None)
    vehiculo.marca = "Cambio pendiente del llamador"

    with pytest.raises(CupoDiarioNoConfiguradoError) as error:
        registrar_orden_sin_confirmar(db_ordenes, vehiculo.vehiculo_id, ADMIN)

    db_ordenes.rollback()
    db_ordenes.expire_all()
    assert db_ordenes.get(Vehiculo, vehiculo.vehiculo_id).marca == "Toyota"
    assert error.value.rechazo.resultado == "cupo_no_configurado"
    assert _conteos(db_ordenes)["validaciones"] == 0


# ── crear_orden y POST /ordenes ────────────────────────────────────────────


def test_exito_confirma_ingreso_orden_historial_outbox_y_validacion(
    api_ordenes: TestClient, db_ordenes: Session
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)

    respuesta = _post(api_ordenes, vehiculo)

    assert respuesta.status_code == 201
    assert respuesta.json()["estado_codigo"] == 1
    assert respuesta.json()["mecanico_actual_id"] is None
    assert _conteos(db_ordenes) == {
        "ingresos": 1, "ordenes": 1, "historial": 1, "outbox": 1, "validaciones": 1,
    }
    validacion = db_ordenes.scalar(select(HistorialValidacionCupoIngreso))
    assert (validacion.aceptada, validacion.resultado) == (True, "cupo_disponible")
    assert validacion.ingreso_id == respuesta.json()["ingreso_id"]


def test_reutiliza_el_ingreso_abierto_sin_validar_cupo(
    api_ordenes: TestClient, db_ordenes: Session
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    primera = _post(api_ordenes, vehiculo)
    _fijar_cupo(db_ordenes, 1)  # el cupo ya está usado por el primer ingreso

    segunda = _post(api_ordenes, vehiculo)

    assert segunda.status_code == 201
    assert segunda.json()["ingreso_id"] == primera.json()["ingreso_id"]
    assert _conteos(db_ordenes) == {
        "ingresos": 1, "ordenes": 2, "historial": 2, "outbox": 2, "validaciones": 1,
    }


@pytest.mark.parametrize("fallo_en", ["historial", "outbox"])
def test_fallo_despues_de_crear_el_ingreso_deshace_todo(
    api_ordenes: TestClient,
    db_ordenes: Session,
    monkeypatch: pytest.MonkeyPatch,
    fallo_en: str,
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    antes = _conteos(db_ordenes)
    flush_real = db_ordenes.flush

    def flush_con_fallo(*args, **kwargs):
        nuevos = list(db_ordenes.new)
        if fallo_en == "historial" and any(isinstance(o, HistorialEstado) for o in nuevos):
            raise SQLAlchemyError("fallo simulado al guardar el historial")
        if fallo_en == "outbox" and any(isinstance(o, EventoOutbox) for o in nuevos):
            raise SQLAlchemyError("fallo simulado al guardar el evento")
        return flush_real(*args, **kwargs)

    monkeypatch.setattr(db_ordenes, "flush", flush_con_fallo)
    respuesta = _post(api_ordenes, vehiculo)
    monkeypatch.setattr(db_ordenes, "flush", flush_real)

    assert respuesta.status_code == 500
    assert respuesta.json() == {"detail": "No fue posible crear la orden"}
    # Ni el ingreso nuevo ni su validación aceptada sobreviven.
    assert _conteos(db_ordenes) == antes


def test_fallo_al_confirmar_deshace_todo(
    api_ordenes: TestClient, db_ordenes: Session, monkeypatch: pytest.MonkeyPatch
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    antes = _conteos(db_ordenes)
    commit_real = db_ordenes.commit

    def commit_fallido():
        raise SQLAlchemyError("fallo simulado al confirmar")

    monkeypatch.setattr(db_ordenes, "commit", commit_fallido)
    respuesta = _post(api_ordenes, vehiculo)
    monkeypatch.setattr(db_ordenes, "commit", commit_real)

    assert respuesta.status_code == 500
    assert _conteos(db_ordenes) == antes


@pytest.mark.parametrize(
    ("maximo", "ingresos_previos", "resultado", "mensaje"),
    [
        (None, 0, "cupo_no_configurado",
         "Configura el máximo diario de ingresos físicos antes de recibir vehículos"),
        (1, 1, "cupo_excedido", "El taller ya alcanzó el máximo diario de ingresos físicos"),
    ],
)
def test_rechazo_de_cupo_deshace_y_audita_los_datos_originales(
    api_ordenes: TestClient,
    db_ordenes: Session,
    maximo,
    ingresos_previos: int,
    resultado: str,
    mensaje: str,
):
    if ingresos_previos:
        assert _post(api_ordenes, _crear_vehiculo(db_ordenes, usuario_cliente=20)).status_code == 201
    _fijar_cupo(db_ordenes, maximo)
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    antes = _conteos(db_ordenes)

    respuesta = _post(api_ordenes, vehiculo)

    assert respuesta.status_code == 409
    assert respuesta.json() == {"detail": mensaje}
    despues = _conteos(db_ordenes)
    assert {k: v for k, v in despues.items() if k != "validaciones"} == {
        k: v for k, v in antes.items() if k != "validaciones"
    }
    assert despues["validaciones"] == antes["validaciones"] + 1
    rechazo = db_ordenes.scalars(
        select(HistorialValidacionCupoIngreso).order_by(
            HistorialValidacionCupoIngreso.validacion_id.desc()
        )
    ).first()
    assert (rechazo.aceptada, rechazo.resultado) == (False, resultado)
    assert rechazo.vehiculo_id == vehiculo.vehiculo_id
    assert rechazo.ingreso_id is None
    assert rechazo.ingresos_registrados == ingresos_previos
    assert rechazo.max_ingresos_diarios == maximo
    assert rechazo.administrador_id == ADMIN


def test_si_falla_la_auditoria_del_rechazo_responde_500_sin_registros(
    api_ordenes: TestClient, db_ordenes: Session, monkeypatch: pytest.MonkeyPatch
):
    _fijar_cupo(db_ordenes, None)
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    antes = _conteos(db_ordenes)
    commit_real = db_ordenes.commit

    def commit_fallido():
        raise SQLAlchemyError("fallo simulado al auditar")

    monkeypatch.setattr(db_ordenes, "commit", commit_fallido)
    respuesta = _post(api_ordenes, vehiculo)
    monkeypatch.setattr(db_ordenes, "commit", commit_real)

    assert respuesta.status_code == 500
    assert respuesta.json() == {"detail": "No fue posible crear la orden"}
    assert _conteos(db_ordenes) == antes


def test_crear_orden_propaga_el_rechazo_con_sus_datos(db_ordenes: Session):
    _fijar_cupo(db_ordenes, None)
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)

    with pytest.raises(CupoDiarioNoConfiguradoError) as error:
        crear_orden(db_ordenes, vehiculo.vehiculo_id, ADMIN)

    assert error.value.rechazo.vehiculo_id == vehiculo.vehiculo_id
    assert _conteos(db_ordenes)["validaciones"] == 1


def test_la_validacion_ya_no_confirma_por_si_misma(
    db_ordenes: Session, monkeypatch: pytest.MonkeyPatch
):
    _fijar_cupo(db_ordenes, 1)
    _crear_vehiculo(db_ordenes, usuario_cliente=10)
    db_ordenes.add(IngresoVehiculo(vehiculo_id=1, registrado_por_id=ADMIN))
    db_ordenes.commit()
    commits = []
    monkeypatch.setattr(db_ordenes, "commit", lambda: commits.append(1))

    with pytest.raises(CupoDiarioExcedidoError):
        servicio_cupo.validar_cupo_para_nuevo_ingreso(
            db_ordenes, vehiculo_id=1, administrador_id=ADMIN
        )

    assert commits == []
    db_ordenes.rollback()


def test_error_de_persistencia_del_nucleo_se_traduce(db_ordenes: Session, monkeypatch):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)

    def fallar(*_a, **_k):
        raise SQLAlchemyError("base caída")

    monkeypatch.setattr(db_ordenes, "flush", fallar)
    with pytest.raises(PersistenciaOrdenError):
        crear_orden(db_ordenes, vehiculo.vehiculo_id, ADMIN)
