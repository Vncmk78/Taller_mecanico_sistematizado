"""Contratos HTTP de la bitácora de trabajo del mecánico.

Una entrada es una observación (nota libre) o una acción (trabajo realizado).
Solo una acción puede declarar los repuestos utilizados, como texto libre y
cantidad: la bitácora no referencia el catálogo de MS3 (§8).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TipoEntrada = Literal["observacion", "accion"]


class RepuestoBitacoraEntrada(BaseModel):
    """Repuesto utilizado en una acción, indicado por su nombre y cantidad."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    nombre: str = Field(min_length=1, max_length=120)
    cantidad: int = Field(gt=0)


class BitacoraCrear(BaseModel):
    """Datos que el mecánico aporta al registrar una entrada de la bitácora."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    tipo: TipoEntrada
    descripcion: str = Field(
        min_length=1,
        description="Texto de la observación o de la acción realizada.",
    )
    repuestos: list[RepuestoBitacoraEntrada] = Field(
        default_factory=list,
        max_length=50,
        description="Repuestos utilizados; solo válido cuando tipo es 'accion'.",
    )

    @model_validator(mode="after")
    def _repuestos_solo_en_acciones(self) -> "BitacoraCrear":
        if self.repuestos and self.tipo != "accion":
            raise ValueError("Solo una acción puede registrar repuestos utilizados")
        return self


class RepuestoBitacoraRespuesta(BaseModel):
    """Repuesto utilizado, tal como queda registrado en la bitácora."""

    model_config = ConfigDict(from_attributes=True)

    nombre: str
    cantidad: int


class BitacoraRespuesta(BaseModel):
    """Representación de una entrada de la bitácora expuesta por la API de MS2."""

    model_config = ConfigDict(from_attributes=True)

    bitacora_id: int
    orden_id: int
    autor_usuario_id: int
    tipo: TipoEntrada
    descripcion: str
    creado_en: datetime
    repuestos: list[RepuestoBitacoraRespuesta] = Field(default_factory=list)
