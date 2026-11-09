"""Contratos HTTP para creación y consulta inicial de órdenes de trabajo."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrdenCrear(BaseModel):
    """Único dato que un administrador puede aportar al crear una orden."""

    model_config = ConfigDict(extra="forbid")

    vehiculo_id: int = Field(gt=0)


class AsignacionMecanicoActualizar(BaseModel):
    """Datos controlables al asignar o reasignar el responsable de una orden."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    mecanico_id: int = Field(gt=0)
    observacion: str | None = Field(default=None, min_length=1)


class CapacidadMecanicoActualizar(BaseModel):
    """Límite administrativo de órdenes activas asignadas a cada mecánico."""

    model_config = ConfigDict(extra="forbid")

    max_ordenes_activas: int = Field(gt=0, strict=True)


class MecanicoSobreLimite(BaseModel):
    """Mecánico cuya carga activa supera el máximo configurado."""

    mecanico_id: int
    ordenes_activas: int


class CapacidadMecanicoRespuesta(BaseModel):
    """Límite vigente y carga que supera el valor recién configurado."""

    model_config = ConfigDict(from_attributes=True)

    max_ordenes_activas: int | None
    actualizado_por_id: int | None
    actualizado_en: datetime
    mecanicos_sobre_limite: list[MecanicoSobreLimite]


class CupoDiarioIngresosActualizar(BaseModel):
    """Límite administrativo de ingresos físicos por jornada local."""

    model_config = ConfigDict(extra="forbid")

    max_ingresos_diarios: int = Field(gt=0, strict=True)


class CupoDiarioIngresosRespuesta(BaseModel):
    """Configuración diaria y uso del cupo en la jornada local actual."""

    model_config = ConfigDict(from_attributes=True)

    max_ingresos_diarios: int | None
    actualizado_por_id: int | None
    actualizado_en: datetime
    jornada_local: date
    ingresos_registrados: int
    sobre_limite: bool


class OrdenRespuesta(BaseModel):
    """Representación inicial de una orden expuesta por la API de MS2."""

    model_config = ConfigDict(from_attributes=True)

    orden_id: int
    vehiculo_id: int
    ingreso_id: int
    estado_codigo: int
    mecanico_actual_id: int | None
    creado_por_id: int
    creado_en: datetime
    actualizado_en: datetime
    devuelto_en: datetime | None
    devuelto_por_id: int | None

    @field_validator("devuelto_en")
    @classmethod
    def fecha_devolucion_con_zona(cls, valor: datetime | None) -> datetime | None:
        # SQLite (solo pruebas) pierde el tzinfo de DateTime(timezone=True).
        # Las fechas de esa base se generan en UTC; PostgreSQL conserva la zona.
        if valor is not None and valor.tzinfo is None:
            return valor.replace(tzinfo=timezone.utc)
        return valor


class DevolucionSolicitud(BaseModel):
    """Confirmación física: no acepta identidad, fecha ni estado del cliente."""

    model_config = ConfigDict(extra="forbid")


class DevolucionOrdenRespuesta(OrdenRespuesta):
    """Orden cancelada y auditoría original de su devolución física."""

    devuelto_en: datetime
    devuelto_por_id: int = Field(gt=0)


class EntregaOrdenRespuesta(OrdenRespuesta):
    """Confirmación auditable de una entrega física de vehículo."""

    model_config = ConfigDict(from_attributes=True)

    orden_id: int
    estado_codigo: int
    entregado_en: datetime
    entregado_por_id: int
    historial_id: int


class DisponibilidadRepuestosRespuesta(BaseModel):
    """Confirmación de la transición basada en reserva verificada por MS3."""

    model_config = ConfigDict(extra="forbid", strict=True)

    clave_operacion: str
    orden_id: int
    estado_aplicado: int
    historial_id: int


class HistorialOrdenesVehiculoRespuesta(BaseModel):
    """Página del historial de órdenes visibles de un vehículo."""

    model_config = ConfigDict(from_attributes=True)

    items: list[OrdenRespuesta]
    total: int
    limit: int
    offset: int
class EntregaSolicitud(BaseModel):
    """Datos controlables al registrar la entrega física de una orden."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    observacion: str | None = Field(
        default=None,
        min_length=1,
        description="Comentario opcional de la entrega.",
    )


class CancelacionClienteSolicitud(BaseModel):
    """Motivo obligatorio con el que el cliente solicita cancelar su orden."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    motivo: str = Field(
        min_length=1,
        description="Motivo de la cancelación; no puede estar vacío.",
    )


class SolicitudCancelacionRespuesta(BaseModel):
    """Solicitud con actor y tiempos para revisión administrativa."""

    model_config = ConfigDict(from_attributes=True)

    solicitud_id: int
    orden_id: int
    cliente_usuario_id: int
    estado_al_solicitar: int
    motivo: str
    estado: Literal["pendiente", "confirmada"]
    solicitada_en: datetime
    administrador_id: int | None
    confirmada_en: datetime | None


class CambioEstadoSolicitud(BaseModel):
    """Datos controlables al solicitar un cambio de estado de una orden."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    # Sin tope superior: el catálogo oficial (1 a 8) lo valida el dominio, que
    # es quien conoce los estados y las transiciones permitidas.
    estado_destino: int = Field(gt=0)
    observacion: str | None = Field(
        default=None,
        min_length=1,
        description="Obligatoria al pasar a Cancelado; opcional en los demás destinos.",
    )


class HistorialEstadoRespuesta(BaseModel):
    """Registro inmutable de un cambio de estado de una orden."""

    model_config = ConfigDict(from_attributes=True)

    historial_id: int
    orden_id: int
    estado_anterior: int | None
    estado_nuevo: int
    actor_usuario_id: int | None
    origen: Literal["usuario", "sistema"]
    fecha_hora: datetime
    observacion: str | None
