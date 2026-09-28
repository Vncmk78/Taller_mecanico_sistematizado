"""Validación estructural del ciclo de vida de una orden de trabajo.

Este módulo contiene la única tabla ejecutable de transiciones de MS2. Solo
responde si un evento puede llevar estructuralmente una orden desde su estado
actual al destino declarado. No consulta bases de datos o servicios externos,
no modifica modelos ORM y no controla precondiciones futuras de presupuesto,
stock, capacidad o autorización.

Fuente funcional: Sistematización final, secciones 4.1 a 4.3 y 4.8.
Diseño técnico: ``backend/docs/maquina-estados-ordenes.md``.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Final, Mapping

from services.ms2_taller.models.estado_orden import (
    CANCELADO,
    EN_REPARACION,
    ENTREGADO,
    ESPERANDO_APROBACION_PRESUPUESTO,
    ESPERANDO_DIAGNOSTICO,
    ESPERANDO_REPUESTOS,
    ESTADOS_ORDEN,
    ESTADOS_TERMINALES,
    LISTO,
    RECIBIDO,
)


class ErrorValidacionTransicion(Exception):
    """Error de dominio base para validaciones del estado de una orden."""


class EstadoOrdenDesconocidoError(ErrorValidacionTransicion):
    """El código recibido no pertenece al catálogo oficial de estados."""


class EventoOrdenDesconocidoError(ErrorValidacionTransicion):
    """El evento recibido no forma parte del contrato del validador."""


class TransicionOrdenNoPermitidaError(ErrorValidacionTransicion):
    """La combinación de estado y evento o destino no está declarada."""


class TransicionOrdenTerminalError(TransicionOrdenNoPermitidaError):
    """Una orden entregada o cancelada no puede cambiar de estado."""


class EventoOrden(StrEnum):
    """Hechos de negocio que pueden producir una transición estructural."""

    CREACION = "creacion"
    PRIMERA_ASIGNACION = "primera_asignacion"
    ENVIO_PRIMER_PRESUPUESTO = "envio_primer_presupuesto"
    PRIMERA_APROBACION_CON_REPUESTOS = "primera_aprobacion_con_repuestos"
    PRIMERA_APROBACION_SIN_REPUESTOS = "primera_aprobacion_sin_repuestos"
    DISPONIBILIDAD_REPUESTOS = "disponibilidad_repuestos"
    FINALIZACION_TRABAJO = "finalizacion_trabajo"
    ENTREGA_FISICA = "entrega_fisica"
    RECHAZO_PRIMER_PRESUPUESTO = "rechazo_primer_presupuesto"
    CANCELACION_SOLICITADA_CONFIRMADA = "cancelacion_solicitada_confirmada"


# Única fuente ejecutable de transiciones permitidas. ``None`` representa que
# la orden todavía no existe; solo el evento CREACION admite ese origen.
TRANSICIONES_PERMITIDAS: Final[
    Mapping[tuple[int | None, EventoOrden], int]
] = MappingProxyType(
    {
        (None, EventoOrden.CREACION): RECIBIDO,
        (RECIBIDO, EventoOrden.PRIMERA_ASIGNACION): ESPERANDO_DIAGNOSTICO,
        (
            ESPERANDO_DIAGNOSTICO,
            EventoOrden.ENVIO_PRIMER_PRESUPUESTO,
        ): ESPERANDO_APROBACION_PRESUPUESTO,
        (
            ESPERANDO_APROBACION_PRESUPUESTO,
            EventoOrden.PRIMERA_APROBACION_CON_REPUESTOS,
        ): EN_REPARACION,
        (
            ESPERANDO_APROBACION_PRESUPUESTO,
            EventoOrden.PRIMERA_APROBACION_SIN_REPUESTOS,
        ): ESPERANDO_REPUESTOS,
        (
            ESPERANDO_REPUESTOS,
            EventoOrden.DISPONIBILIDAD_REPUESTOS,
        ): EN_REPARACION,
        (EN_REPARACION, EventoOrden.FINALIZACION_TRABAJO): LISTO,
        (LISTO, EventoOrden.ENTREGA_FISICA): ENTREGADO,
        (
            ESPERANDO_APROBACION_PRESUPUESTO,
            EventoOrden.RECHAZO_PRIMER_PRESUPUESTO,
        ): CANCELADO,
        (
            RECIBIDO,
            EventoOrden.CANCELACION_SOLICITADA_CONFIRMADA,
        ): CANCELADO,
        (
            ESPERANDO_DIAGNOSTICO,
            EventoOrden.CANCELACION_SOLICITADA_CONFIRMADA,
        ): CANCELADO,
        (
            ESPERANDO_APROBACION_PRESUPUESTO,
            EventoOrden.CANCELACION_SOLICITADA_CONFIRMADA,
        ): CANCELADO,
    }
)


def resolver_transicion(
    estado_actual: int | None,
    evento: EventoOrden,
) -> int:
    """Valida ``estado_actual + evento`` y devuelve el estado de destino.

    El resultado no se persiste ni se aplica a una ``OrdenTrabajo``. Quien
    coordine la operación es responsable de comprobar sus precondiciones y de
    actualizar estado e historial dentro de una misma transacción.
    """

    if not isinstance(evento, EventoOrden):
        raise EventoOrdenDesconocidoError(
            f"Evento de orden desconocido: {evento!r}"
        )

    if estado_actual is not None:
        validar_estado_no_terminal(estado_actual)

    try:
        return TRANSICIONES_PERMITIDAS[(estado_actual, evento)]
    except KeyError as exc:
        if estado_actual is None:
            estado_nombre = "sin orden"
        else:
            estado_nombre = ESTADOS_ORDEN[estado_actual]
        raise TransicionOrdenNoPermitidaError(
            f"Evento {evento.value!r} no permitido desde {estado_nombre}"
        ) from exc


def validar_transicion(estado_actual: int, estado_destino: int) -> None:
    """Valida un par estructural sin duplicar la tabla definida por evento."""

    _validar_estado_conocido(estado_actual, campo="origen")
    _validar_estado_conocido(estado_destino, campo="destino")
    validar_estado_no_terminal(estado_actual)

    if any(
        origen == estado_actual and destino == estado_destino
        for (origen, _evento), destino in TRANSICIONES_PERMITIDAS.items()
    ):
        return

    raise TransicionOrdenNoPermitidaError(
        "Transición no permitida: "
        f"{ESTADOS_ORDEN[estado_actual]} -> {ESTADOS_ORDEN[estado_destino]}"
    )


def validar_estado_no_terminal(estado_actual: int) -> None:
    """Rechaza estados desconocidos y cualquier salida desde un terminal."""

    _validar_estado_conocido(estado_actual, campo="origen")
    if estado_actual in ESTADOS_TERMINALES:
        raise TransicionOrdenTerminalError(
            f"El estado {ESTADOS_ORDEN[estado_actual]} es terminal y no admite "
            "transiciones"
        )


def _validar_estado_conocido(estado: int, *, campo: str) -> None:
    if estado not in ESTADOS_ORDEN:
        raise EstadoOrdenDesconocidoError(
            f"Estado de {campo} desconocido: {estado!r}"
        )
