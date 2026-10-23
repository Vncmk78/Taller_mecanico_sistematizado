"""Contratos públicos de integración de inventario publicados por MS3."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RepuestoReservado(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    repuesto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)


class DisponibilidadRepuestosRespuesta(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    clave_operacion: str = Field(min_length=1, max_length=100)
    orden_id: int = Field(gt=0)
    version_presupuesto: int = Field(gt=0)
    repuestos: list[RepuestoReservado]
    aplicacion_confirmada: Literal[True]
