"""Contrato mínimo de coordinación síncrona MS3–MS2 (sin modelos ORM)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DecisionOrdenSolicitud(BaseModel):
    """Solo una referencia: MS2 consulta los hechos directamente en MS3."""

    model_config = ConfigDict(extra="forbid")

    decision_id: int = Field(gt=0)


class EnvioPresupuestoSolicitud(BaseModel):
    """Referencia al presupuesto cuyo envío inicial activó la orden."""

    model_config = ConfigDict(extra="forbid")

    presupuesto_id: int = Field(gt=0)


class DisponibilidadRepuestosSolicitud(BaseModel):
    """Clave estable de la reserva confirmada en MS3."""

    model_config = ConfigDict(extra="forbid", strict=True)

    clave_operacion: str = Field(min_length=1, max_length=100)


class DisponibilidadRepuestosVerificada(BaseModel):
    """Hecho de MS3: la reserva de repuestos quedó persistida para la orden."""

    model_config = ConfigDict(extra="forbid", strict=True)

    clave_operacion: str = Field(min_length=1, max_length=100)
    orden_id: int = Field(gt=0)
    reserva_confirmada: Literal[True]


class AplicacionDisponibilidadRepuestosRespuesta(BaseModel):
    """Transición a reparación aplicada en MS2, también ante reintentos."""

    model_config = ConfigDict(extra="forbid", strict=True)

    clave_operacion: str = Field(min_length=1, max_length=100)
    orden_id: int = Field(gt=0)
    estado_aplicado: int = Field(ge=1, le=8)
    historial_id: int = Field(gt=0)


class EnvioPresupuestoVerificado(BaseModel):
    """Hecho persistido por MS3: hay un presupuesto inicial enviado."""

    model_config = ConfigDict(extra="forbid", strict=True)

    presupuesto_id: int = Field(gt=0)
    orden_id: int = Field(gt=0)
    envio_inicial_confirmado: Literal[True]


class AplicacionEnvioPresupuestoRespuesta(BaseModel):
    """Transición inicial ya aplicada en MS2, incluso cuando se reintenta."""

    model_config = ConfigDict(extra="forbid", strict=True)

    presupuesto_id: int = Field(gt=0)
    orden_id: int = Field(gt=0)
    estado_aplicado: int = Field(ge=1, le=8)
    historial_id: int = Field(gt=0)


class DecisionPresupuestoVerificada(BaseModel):
    """Hecho persistido de MS3, visible únicamente para su cliente responsable."""

    model_config = ConfigDict(extra="forbid", strict=True)

    decision_id: int = Field(gt=0)
    orden_id: int = Field(gt=0)
    cliente_usuario_id: int = Field(gt=0)
    decision: Literal["aprobado", "rechazado"]
    primera_decision: bool
    # Evaluación guardada al decidir; no se recalcula con el stock del reintento.
    repuestos_disponibles: bool | None
    motivo: str | None


class AplicacionDecisionRespuesta(BaseModel):
    """Efecto ya aplicado, también cuando la petición es un reintento."""

    model_config = ConfigDict(extra="forbid", strict=True)

    decision_id: int = Field(gt=0)
    orden_id: int = Field(gt=0)
    estado_aplicado: int = Field(ge=1, le=8)
    historial_id: int = Field(gt=0)


class DecisionAplicacionPendiente(BaseModel):
    """La decisión existe, pero MS3 no puede confirmar el efecto en MS2."""

    detail: str
    decision_id: int
    orden_id: int
    decision_registrada: Literal[True] = True
    aplicacion_confirmada: Literal[False] = False
    reintento: str
    estado_ms2: int | None = None
    detalle_ms2: str | None = None


class EnvioPresupuestoAplicacionPendiente(BaseModel):
    """MS3 confirmó el envío; MS2 aún no confirmó la transición de la orden."""

    detail: str
    presupuesto_id: int
    orden_id: int
    envio_confirmado: Literal[True] = True
    aplicacion_confirmada: Literal[False] = False
    reintento: str
    estado_ms2: int | None = None
    detalle_ms2: str | None = None
