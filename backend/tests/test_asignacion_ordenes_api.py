"""Pruebas HTTP de asignación y reasignación de órdenes (INT-33)."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms2_taller.config import settings
from services.ms2_taller.db import get_db
from services.ms2_taller.main import app
from services.ms2_taller.models import (
    Base,
    Cliente,
    EstadoOrden,
    HistorialAsignacion,
    HistorialEstado,
    IngresoVehiculo,
    OrdenTrabajo,
    Vehiculo,
)
from services.ms2_taller.models.estado_orden import (
    CANCELADO,
    EN_REPARACION,
    ENTREGADO,
    ESPERANDO_DIAGNOSTICO,
    ESTADOS_ORDEN,
    RECIBIDO,
)
from services.ms2_taller.services.ordenes import (
    _consulta_orden_para_actualizacion,
)
from shared.auth import NombreRol, crear_token_acceso


@pytest.fixture
def db_asignaciones() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def registrar_funciones_sqlite(conexion, _registro) -> None:
        conexion.create_function(
            "btrim",
            1,
            lambda valor: valor.strip() if valor is not None else None,
        )
        conexion.create_function(
            "char_length",
            1,
            lambda valor: len(valor) if valor is not None else None,
        )

    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    sesion = fabrica()
    sesion.add_all(
        [
            EstadoOrden(estado_codigo=codigo, nombre=nombre)
            for codigo, nombre in ESTADOS_ORDEN.items()
        ]
    )
    sesion.commit()
    try:
        yield sesion
    finally:
        sesion.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def api_asignaciones(
    db_asignaciones: Session,
) -> Generator[TestClient, None, None]:
    def reemplazar_db():
        yield db_asignaciones

    app.dependency_overrides[get_db] = reemplazar_db
    with TestClient(app) as cliente_http:
        yield cliente_http
    app.dependency_overrides.clear()


def test_primera_asignacion_cambia_estado_y_registra_ambos_historiales(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
):
    orden = _crear_orden(db_asignaciones)

    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50, "observacion": "  Primera asignación  "},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["mecanico_actual_id"] == 50
    assert respuesta.json()["estado_codigo"] == ESPERANDO_DIAGNOSTICO

    db_asignaciones.expire_all()
    persistida = db_asignaciones.get(OrdenTrabajo, orden.orden_id)
    historial_asignacion = db_asignaciones.scalar(select(HistorialAsignacion))
    historial_estado = db_asignaciones.scalar(select(HistorialEstado))
    assert persistida is not None
    assert persistida.mecanico_actual_id == 50
    assert persistida.estado_codigo == ESPERANDO_DIAGNOSTICO
    assert historial_asignacion is not None
    assert historial_asignacion.orden_id == orden.orden_id
    assert historial_asignacion.mecanico_anterior_id is None
    assert historial_asignacion.mecanico_nuevo_id == 50
    assert historial_asignacion.administrador_id == 99
    assert historial_asignacion.fecha_hora is not None
    assert historial_asignacion.observacion == "Primera asignación"
    assert historial_estado is not None
    assert historial_estado.orden_id == orden.orden_id
    assert historial_estado.estado_anterior == RECIBIDO
    assert historial_estado.estado_nuevo == ESPERANDO_DIAGNOSTICO
    assert historial_estado.actor_usuario_id == 99
    assert historial_estado.origen == "usuario"
    assert historial_estado.fecha_hora is not None


def test_administrador_reasigna_y_conserva_responsable_anterior(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
):
    orden = _crear_orden(
        db_asignaciones,
        mecanico_id=40,
        estado_codigo=EN_REPARACION,
    )

    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["mecanico_actual_id"] == 50
    assert respuesta.json()["estado_codigo"] == EN_REPARACION
    historial = db_asignaciones.scalar(select(HistorialAsignacion))
    assert historial is not None
    assert historial.mecanico_anterior_id == 40
    assert historial.mecanico_nuevo_id == 50
    assert historial.administrador_id == 99
    assert db_asignaciones.scalar(
        select(func.count()).select_from(HistorialEstado)
    ) == 0


@pytest.mark.parametrize("rol", [NombreRol.CLIENTE, NombreRol.MECANICO])
def test_usuario_sin_rol_administrador_recibe_403(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
    rol: NombreRol,
):
    orden = _crear_orden(db_asignaciones)

    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50},
        headers=_headers_para(20, rol),
    )

    assert respuesta.status_code == 403
    db_asignaciones.refresh(orden)
    assert orden.mecanico_actual_id is None
    assert db_asignaciones.scalar(
        select(func.count()).select_from(HistorialAsignacion)
    ) == 0


def test_multirol_con_administrador_puede_asignar_a_otro_usuario(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
):
    orden = _crear_orden(db_asignaciones)

    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50},
        headers=_headers_para(
            99,
            NombreRol.CLIENTE,
            NombreRol.MECANICO,
            NombreRol.ADMINISTRADOR,
        ),
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["mecanico_actual_id"] == 50


def test_administrador_mecanico_no_puede_autoasignarse(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
):
    orden = _crear_orden(db_asignaciones)

    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 99},
        headers=_headers_para(
            99,
            NombreRol.MECANICO,
            NombreRol.ADMINISTRADOR,
        ),
    )

    assert respuesta.status_code == 409
    assert respuesta.json() == {
        "detail": "Un mecánico no puede autoasignarse una orden"
    }
    db_asignaciones.refresh(orden)
    assert orden.mecanico_actual_id is None


def test_orden_inexistente_devuelve_404(api_asignaciones: TestClient):
    respuesta = api_asignaciones.put(
        "/ordenes/999/mecanico",
        json={"mecanico_id": 50},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Orden no encontrada"}


def test_asignacion_sin_token_devuelve_401(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
):
    orden = _crear_orden(db_asignaciones)

    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50},
    )

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("mecanico_id", [0, -1])
def test_mecanico_id_debe_ser_positivo(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
    mecanico_id: int,
):
    orden = _crear_orden(db_asignaciones)

    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": mecanico_id},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 422
    db_asignaciones.refresh(orden)
    assert orden.mecanico_actual_id is None


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("administrador_id", 99),
        ("mecanico_anterior_id", 40),
        ("fecha_hora", "2026-09-23T12:00:00Z"),
        ("estado_codigo", 2),
    ],
)
def test_body_rechaza_campos_controlados_por_servidor(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
    campo: str,
    valor: object,
):
    orden = _crear_orden(db_asignaciones)

    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50, campo: valor},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 422
    db_asignaciones.refresh(orden)
    assert orden.mecanico_actual_id is None


def test_repetir_mismo_mecanico_es_idempotente(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
):
    orden = _crear_orden(db_asignaciones)
    ruta = f"/ordenes/{orden.orden_id}/mecanico"
    headers = _headers_para(99, NombreRol.ADMINISTRADOR)

    primera = api_asignaciones.put(
        ruta,
        json={"mecanico_id": 50},
        headers=headers,
    )
    segunda = api_asignaciones.put(
        ruta,
        json={"mecanico_id": 50, "observacion": "No debe registrarse"},
        headers=headers,
    )

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["mecanico_actual_id"] == 50
    assert db_asignaciones.scalar(
        select(func.count()).select_from(HistorialAsignacion)
    ) == 1
    assert db_asignaciones.scalar(
        select(func.count()).select_from(HistorialEstado)
    ) == 1


def test_fallo_en_primera_asignacion_revierte_mecanico_estado_e_historiales(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    orden = _crear_orden(db_asignaciones)
    flush_real = db_asignaciones.flush

    def fallar_flush(*args, **kwargs) -> None:
        raise SQLAlchemyError("fallo simulado al crear historial")

    monkeypatch.setattr(db_asignaciones, "flush", fallar_flush)
    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 500
    monkeypatch.setattr(db_asignaciones, "flush", flush_real)
    db_asignaciones.expire_all()
    persistida = db_asignaciones.get(OrdenTrabajo, orden.orden_id)
    assert persistida is not None
    assert persistida.mecanico_actual_id is None
    assert persistida.estado_codigo == RECIBIDO
    assert db_asignaciones.scalar(
        select(func.count()).select_from(HistorialAsignacion)
    ) == 0
    assert db_asignaciones.scalar(
        select(func.count()).select_from(HistorialEstado)
    ) == 0


def test_nuevo_mecanico_obtiene_visibilidad_por_get(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
):
    orden = _crear_orden(db_asignaciones)
    asignacion = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    detalle = api_asignaciones.get(
        f"/ordenes/{orden.orden_id}",
        headers=_headers_para(50, NombreRol.MECANICO),
    )

    assert asignacion.status_code == 200
    assert detalle.status_code == 200
    assert detalle.json()["orden_id"] == orden.orden_id


def test_mecanico_anterior_pierde_visibilidad_tras_reasignacion(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
):
    orden = _crear_orden(db_asignaciones, mecanico_id=40)
    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    detalle_anterior = api_asignaciones.get(
        f"/ordenes/{orden.orden_id}",
        headers=_headers_para(40, NombreRol.MECANICO),
    )
    detalle_nuevo = api_asignaciones.get(
        f"/ordenes/{orden.orden_id}",
        headers=_headers_para(50, NombreRol.MECANICO),
    )

    assert respuesta.status_code == 200
    assert detalle_anterior.status_code == 404
    assert detalle_nuevo.status_code == 200


def test_primera_asignacion_actualiza_estado_y_crea_historial_estado(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
):
    orden = _crear_orden(db_asignaciones)

    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado_codigo"] == ESPERANDO_DIAGNOSTICO
    db_asignaciones.refresh(orden)
    assert orden.estado_codigo == ESPERANDO_DIAGNOSTICO
    assert db_asignaciones.scalar(
        select(func.count()).select_from(HistorialEstado)
    ) == 1


@pytest.mark.parametrize("estado_codigo", [ENTREGADO, CANCELADO])
@pytest.mark.parametrize("mecanico_actual_id", [None, 40])
def test_estado_terminal_rechaza_asignacion_y_reasignacion(
    api_asignaciones: TestClient,
    db_asignaciones: Session,
    estado_codigo: int,
    mecanico_actual_id: int | None,
):
    orden = _crear_orden(
        db_asignaciones,
        mecanico_id=mecanico_actual_id,
        estado_codigo=estado_codigo,
    )

    respuesta = api_asignaciones.put(
        f"/ordenes/{orden.orden_id}/mecanico",
        json={"mecanico_id": 50},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 409
    assert respuesta.json() == {
        "detail": "No se puede cambiar el mecánico de una orden terminal"
    }
    db_asignaciones.expire_all()
    persistida = db_asignaciones.get(OrdenTrabajo, orden.orden_id)
    assert persistida is not None
    assert persistida.estado_codigo == estado_codigo
    assert persistida.mecanico_actual_id == mecanico_actual_id
    assert db_asignaciones.scalar(
        select(func.count()).select_from(HistorialAsignacion)
    ) == 0
    assert db_asignaciones.scalar(
        select(func.count()).select_from(HistorialEstado)
    ) == 0


def test_consulta_de_orden_usa_for_update_en_postgresql():
    consulta = _consulta_orden_para_actualizacion(123)

    sql = " ".join(
        str(
            consulta.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).split()
    )

    assert "WHERE orden_trabajo.orden_id = 123" in sql
    assert sql.endswith("FOR UPDATE OF orden_trabajo")


def _crear_orden(
    db: Session,
    *,
    mecanico_id: int | None = None,
    estado_codigo: int = RECIBIDO,
) -> OrdenTrabajo:
    cliente = Cliente(usuario_id=10)
    db.add(cliente)
    db.flush()
    vehiculo = Vehiculo(
        cliente_id=cliente.cliente_id,
        patente="AA0001",
        marca="Toyota",
        modelo="Yaris",
    )
    db.add(vehiculo)
    db.flush()
    ingreso = IngresoVehiculo(
        vehiculo_id=vehiculo.vehiculo_id,
        registrado_por_id=99,
    )
    db.add(ingreso)
    db.flush()
    orden = OrdenTrabajo(
        vehiculo_id=vehiculo.vehiculo_id,
        ingreso_id=ingreso.ingreso_id,
        estado_codigo=estado_codigo,
        mecanico_actual_id=mecanico_id,
        creado_por_id=99,
    )
    db.add(orden)
    db.commit()
    db.refresh(orden)
    return orden


def _headers_para(usuario_id: int, *roles: NombreRol) -> dict[str, str]:
    token = crear_token_acceso(
        usuario_id,
        roles,
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}
