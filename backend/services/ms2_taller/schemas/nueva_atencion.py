"""Contrato de solicitudes de nueva atención, separado del estado de orden."""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SituacionNuevaAtencion = Literal["pendiente", "aceptada", "rechazada"]


class NuevaAtencionSolicitud(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    descripcion: str = Field(min_length=1, max_length=2000)


class SolicitudNuevaAtencionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    solicitud_id: int
    orden_cancelada_id: int
    vehiculo_id: int
    cliente_usuario_id: int
    descripcion: str
    solicitada_en: datetime
    situacion: SituacionNuevaAtencion
    respuesta: str | None
    revisor_id: int | None
    revisada_en: datetime | None
    orden_generada_id: int | None

    @field_validator("solicitada_en", "revisada_en")
    @classmethod
    def fechas_con_zona(cls, valor: datetime | None) -> datetime | None:
        # SQLite de pruebas pierde la zona de los valores generados en UTC.
        if valor is not None and valor.tzinfo is None:
            return valor.replace(tzinfo=timezone.utc)
        return valor


class SolicitudesNuevaAtencionRespuesta(BaseModel):
    items: list[SolicitudNuevaAtencionRespuesta]
    total: int
    limit: int
    offset: int
