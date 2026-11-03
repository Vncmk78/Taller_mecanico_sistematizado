"""Contratos de recepción interna y consulta de avisos."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventoEstadoOrden(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evento_id: UUID
    tipo: Literal["orden.estado_cambiado"]
    ocurrido_en: datetime
    orden_id: int = Field(gt=0)
    vehiculo_id: int = Field(gt=0)
    cliente_usuario_id: int = Field(gt=0)
    estado_anterior: int | None = Field(default=None, gt=0)
    estado_nuevo: int = Field(gt=0)

    @model_validator(mode="after")
    def validar_cambio_real(self) -> "EventoEstadoOrden":
        estados = set(range(1, 9))
        if self.estado_nuevo not in estados or (
            self.estado_anterior is not None and self.estado_anterior not in estados
        ):
            raise ValueError("Los códigos de estado deben pertenecer al catálogo oficial")
        if self.estado_anterior == self.estado_nuevo:
            raise ValueError("El evento debe representar un cambio real de estado")
        return self

    @field_validator("ocurrido_en")
    @classmethod
    def exigir_zona_horaria(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("ocurrido_en debe incluir una zona horaria")
        return valor


class EventoRecibidoRespuesta(BaseModel):
    notificacion_id: int
    evento_id: UUID
    duplicado: bool


class NotificacionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notificacion_id: int
    tipo: str
    orden_id: int
    vehiculo_id: int
    titulo: str
    mensaje: str
    ocurrido_en: datetime
    creado_en: datetime
