"""Contratos HTTP iniciales para vehículos (INT-29)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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


class VehiculoRespuesta(BaseModel):
    """Representación inicial de un vehículo expuesta por la API."""

    model_config = ConfigDict(from_attributes=True)

    vehiculo_id: int
    patente: str
    marca: str
    modelo: str
    anio: int | None
    kilometraje: int | None
