"""Pruebas unitarias de los validadores base de estados de SCRUM-315."""

from __future__ import annotations

import pytest

from services.ms2_taller.domain.transiciones_orden import (
    EstadoOrdenDesconocidoError,
    EventoOrden,
    EventoOrdenDesconocidoError,
    TransicionOrdenNoPermitidaError,
    TransicionOrdenTerminalError,
    resolver_transicion,
    validar_transicion,
)
from services.ms2_taller.models.estado_orden import (
    CANCELADO,
    EN_REPARACION,
    ENTREGADO,
    ESPERANDO_APROBACION_PRESUPUESTO,
    ESPERANDO_DIAGNOSTICO,
    ESPERANDO_REPUESTOS,
    LISTO,
    RECIBIDO,
)
from services.ms2_taller.models.orden_trabajo import OrdenTrabajo


def test_creacion_resuelve_estado_inicial_recibido():
    assert resolver_transicion(None, EventoOrden.CREACION) == RECIBIDO


def test_primera_asignacion_permite_esperando_diagnostico():
    destino = resolver_transicion(RECIBIDO, EventoOrden.PRIMERA_ASIGNACION)

    assert destino == ESPERANDO_DIAGNOSTICO
    validar_transicion(RECIBIDO, destino)


def test_transicion_adicional_de_tabla_es_permitida():
    destino = resolver_transicion(
        ESPERANDO_DIAGNOSTICO,
        EventoOrden.ENVIO_PRIMER_PRESUPUESTO,
    )

    assert destino == ESPERANDO_APROBACION_PRESUPUESTO
    validar_transicion(ESPERANDO_DIAGNOSTICO, destino)


@pytest.mark.parametrize(
    "estado_actual,evento,estado_destino",
    [
        (
            ESPERANDO_APROBACION_PRESUPUESTO,
            EventoOrden.PRIMERA_APROBACION_CON_REPUESTOS,
            EN_REPARACION,
        ),
        (
            ESPERANDO_APROBACION_PRESUPUESTO,
            EventoOrden.PRIMERA_APROBACION_SIN_REPUESTOS,
            ESPERANDO_REPUESTOS,
        ),
        (
            ESPERANDO_REPUESTOS,
            EventoOrden.DISPONIBILIDAD_REPUESTOS,
            EN_REPARACION,
        ),
        (EN_REPARACION, EventoOrden.FINALIZACION_TRABAJO, LISTO),
        (LISTO, EventoOrden.ENTREGA_FISICA, ENTREGADO),
        (
            ESPERANDO_APROBACION_PRESUPUESTO,
            EventoOrden.RECHAZO_PRIMER_PRESUPUESTO,
            CANCELADO,
        ),
        (
            RECIBIDO,
            EventoOrden.CANCELACION_SOLICITADA_CONFIRMADA,
            CANCELADO,
        ),
        (
            ESPERANDO_DIAGNOSTICO,
            EventoOrden.CANCELACION_SOLICITADA_CONFIRMADA,
            CANCELADO,
        ),
        (
            ESPERANDO_APROBACION_PRESUPUESTO,
            EventoOrden.CANCELACION_SOLICITADA_CONFIRMADA,
            CANCELADO,
        ),
    ],
)
def test_tabla_resuelve_transiciones_documentadas(
    estado_actual: int,
    evento: EventoOrden,
    estado_destino: int,
):
    assert resolver_transicion(estado_actual, evento) == estado_destino


def test_transicion_inexistente_es_rechazada():
    with pytest.raises(
        TransicionOrdenNoPermitidaError,
        match="Recibido -> En reparación",
    ):
        validar_transicion(RECIBIDO, EN_REPARACION)


def test_evento_no_permitido_desde_estado_conocido_es_rechazado():
    with pytest.raises(
        TransicionOrdenNoPermitidaError,
        match="no permitido desde Recibido",
    ):
        resolver_transicion(RECIBIDO, EventoOrden.ENTREGA_FISICA)


def test_entregado_rechaza_cualquier_transicion_saliente():
    with pytest.raises(TransicionOrdenTerminalError, match="Entregado es terminal"):
        validar_transicion(ENTREGADO, RECIBIDO)


def test_cancelado_rechaza_cualquier_transicion_saliente():
    with pytest.raises(TransicionOrdenTerminalError, match="Cancelado es terminal"):
        validar_transicion(CANCELADO, RECIBIDO)


@pytest.mark.parametrize("estado_terminal", [ENTREGADO, CANCELADO])
def test_terminal_no_se_reabre_mediante_evento(estado_terminal: int):
    with pytest.raises(TransicionOrdenTerminalError):
        resolver_transicion(
            estado_terminal,
            EventoOrden.PRIMERA_ASIGNACION,
        )


def test_estado_origen_desconocido_es_rechazado():
    with pytest.raises(
        EstadoOrdenDesconocidoError,
        match="Estado de origen desconocido: 999",
    ):
        validar_transicion(999, RECIBIDO)


def test_estado_destino_desconocido_es_rechazado():
    with pytest.raises(
        EstadoOrdenDesconocidoError,
        match="Estado de destino desconocido: 999",
    ):
        validar_transicion(RECIBIDO, 999)


def test_evento_desconocido_es_rechazado_de_forma_controlada():
    with pytest.raises(
        EventoOrdenDesconocidoError,
        match="Evento de orden desconocido",
    ):
        resolver_transicion(RECIBIDO, "evento_inventado")  # type: ignore[arg-type]


def test_validador_no_modifica_orden_trabajo():
    orden = OrdenTrabajo(estado_codigo=RECIBIDO)

    destino = resolver_transicion(
        orden.estado_codigo,
        EventoOrden.PRIMERA_ASIGNACION,
    )

    assert destino == ESPERANDO_DIAGNOSTICO
    assert orden.estado_codigo == RECIBIDO
