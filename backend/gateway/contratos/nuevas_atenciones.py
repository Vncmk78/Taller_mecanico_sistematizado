"""Copia independiente del contrato de solicitudes de MS2 para la Gateway."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from gateway.contratos.ordenes import OrdenRespuesta


class NuevaAtencionSolicitud(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True, extra="forbid",
        json_schema_extra={"examples": [{"descripcion": "Solicito revisar nuevamente los frenos."}]},
    )
    descripcion: str = Field(min_length=1, max_length=2000)


class SolicitudNuevaAtencionRespuesta(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "solicitud_id": 3, "orden_cancelada_id": 25, "vehiculo_id": 9,
        "cliente_usuario_id": 10, "descripcion": "Solicito revisar nuevamente los frenos.",
        "solicitada_en": "2026-11-08T13:00:00Z", "situacion": "pendiente",
        "respuesta": None, "revisor_id": None, "revisada_en": None, "orden_generada_id": None,
    }]})
    solicitud_id: int
    orden_cancelada_id: int
    vehiculo_id: int
    cliente_usuario_id: int
    descripcion: str
    solicitada_en: datetime
    situacion: Literal["pendiente", "aceptada", "rechazada"]
    respuesta: str | None
    revisor_id: int | None
    revisada_en: datetime | None
    orden_generada_id: int | None


class SolicitudesNuevaAtencionRespuesta(BaseModel):
    items: list[SolicitudNuevaAtencionRespuesta]
    total: int
    limit: int
    offset: int


class RevisionNuevaAtencionSolicitud(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    decision: Literal["aceptada", "rechazada"]
    respuesta: str = Field(min_length=1)


class GeneracionNuevaAtencionSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{}]})


class GeneracionNuevaAtencionRespuesta(BaseModel):
    solicitud: SolicitudNuevaAtencionRespuesta
    orden: OrdenRespuesta
