"""Contratos HTTP para registro, consulta y actualización de vehículos."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VehiculoCrear(BaseModel):
    """Datos que el cliente puede proporcionar al registrar un vehículo.

    La identidad del propietario no forma parte del body. El ``Cliente`` debe
    llegar resuelto internamente desde una identidad autenticada.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    patente: str = Field(min_length=1, max_length=10)
    marca: str = Field(min_length=1, max_length=60)
    modelo: str = Field(min_length=1, max_length=60)
    anio: int | None = None
    kilometraje: int | None = None


class VehiculoActualizar(BaseModel):
    """Campos que el Cliente puede modificar parcialmente en su vehículo."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    marca: str | None = Field(default=None, min_length=1, max_length=60)
    modelo: str | None = Field(default=None, min_length=1, max_length=60)
    anio: int | None = None
    kilometraje: int | None = None

    @model_validator(mode="after")
    def validar_campos_enviados(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Debe enviarse al menos un campo para actualizar")
        for campo in {"marca", "modelo"} & self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"{campo} no puede ser nulo")
        return self


class VehiculoRespuesta(BaseModel):
    """Representación inicial de un vehículo expuesta por la API."""

    model_config = ConfigDict(from_attributes=True)

    vehiculo_id: int
    patente: str
    marca: str
    modelo: str
    anio: int | None
    kilometraje: int | None
