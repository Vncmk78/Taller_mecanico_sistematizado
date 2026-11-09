"""Hechos de MS3 para notificaciones; no aceptan destinatarios arbitrarios."""

from datetime import datetime
from typing import Literal, Annotated
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HechoAviso(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evento_id: UUID
    ocurrido_en: datetime

    @field_validator("ocurrido_en")
    @classmethod
    def con_zona(cls, v):
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("La fecha requiere zona horaria")
        return v


class AvisoPresupuestoEnviado(HechoAviso):
    tipo: Literal["presupuesto.enviado"]
    presupuesto_id: int = Field(gt=0)
    orden_id: int = Field(gt=0)
    version: int = Field(gt=0)


class AvisoDecisionPresupuesto(HechoAviso):
    tipo: Literal["presupuesto.decidido"]
    presupuesto_id: int = Field(gt=0)
    orden_id: int = Field(gt=0)
    version: int = Field(gt=0)
    decision_id: int = Field(gt=0)
    decision: Literal["aprobado", "rechazado"]


class AvisoStock(HechoAviso):
    tipo: Literal["stock.alerta"]
    repuesto_id: int = Field(gt=0)
    nombre: str = Field(min_length=1, max_length=200)
    stock: int = Field(ge=0)
    umbral: int = Field(gt=0)

    @model_validator(mode="after")
    def bajo_umbral(self):
        if self.stock >= self.umbral:
            raise ValueError("La alerta requiere stock menor que umbral")
        return self


AvisoMS3 = Annotated[
    AvisoPresupuestoEnviado | AvisoDecisionPresupuesto | AvisoStock, Field(discriminator="tipo")
]


class DestinatarioOrden(BaseModel):
    model_config = ConfigDict(extra="forbid")
    orden_id: int = Field(gt=0)
    vehiculo_id: int = Field(gt=0)
    cliente_usuario_id: int = Field(gt=0)
