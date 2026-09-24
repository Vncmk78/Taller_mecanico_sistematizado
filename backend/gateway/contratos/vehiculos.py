"""Copias de los contratos HTTP de MS2 (Vehículos) para la documentación.

La Gateway no importa código de los microservicios: mantiene sus propias
copias para que `/docs` funcione sin depender de MS2. El test de contrato de
`tests/test_gateway_openapi.py` las compara con los esquemas reales de MS2.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_EJEMPLO_CREAR: dict[str, object] = {
    "patente": "AB1234",
    "marca": "Toyota",
    "modelo": "Corolla",
    "anio": 2018,
    "kilometraje": 45000,
}

_EJEMPLO_ACTUALIZAR: dict[str, object] = {
    "marca": "Toyota",
    "modelo": "Corolla Cross",
}

_EJEMPLO_RESPUESTA: dict[str, object] = {
    "vehiculo_id": 12,
    "patente": "AB1234",
    "marca": "Toyota",
    "modelo": "Corolla",
    "anio": 2018,
    "kilometraje": 45000,
}


class VehiculoCrear(BaseModel):
    """Datos que el cliente envía al registrar su vehículo."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_CREAR]},
    )

    patente: str = Field(
        description="Patente del vehículo.",
        min_length=1,
        max_length=10,
        examples=["AB1234"],
    )
    marca: str = Field(
        description="Marca del vehículo.",
        min_length=1,
        max_length=60,
        examples=["Toyota"],
    )
    modelo: str = Field(
        description="Modelo del vehículo.",
        min_length=1,
        max_length=60,
        examples=["Corolla"],
    )
    anio: int | None = Field(
        default=None,
        description="Año de fabricación (opcional).",
        examples=[2018],
    )
    kilometraje: int | None = Field(
        default=None,
        description="Kilometraje actual (opcional).",
        examples=[45000],
    )


class VehiculoActualizar(BaseModel):
    """Campos que el cliente puede modificar parcialmente en su vehículo.

    Todos son opcionales, pero debe enviarse al menos uno.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_ACTUALIZAR]},
    )

    marca: str | None = Field(
        default=None,
        min_length=1,
        max_length=60,
        description="Nueva marca.",
        examples=["Toyota"],
    )
    modelo: str | None = Field(
        default=None,
        min_length=1,
        max_length=60,
        description="Nuevo modelo.",
        examples=["Corolla Cross"],
    )
    anio: int | None = Field(default=None, description="Nuevo año.", examples=[2020])
    kilometraje: int | None = Field(
        default=None, description="Nuevo kilometraje.", examples=[50000]
    )


class VehiculoRespuesta(BaseModel):
    """Representación de un vehículo expuesta por la API."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EJEMPLO_RESPUESTA]})

    vehiculo_id: int = Field(description="Identificador del vehículo.", examples=[12])
    patente: str = Field(description="Patente del vehículo.", examples=["AB1234"])
    marca: str = Field(description="Marca.", examples=["Toyota"])
    modelo: str = Field(description="Modelo.", examples=["Corolla"])
    anio: int | None = Field(description="Año de fabricación.", examples=[2018])
    kilometraje: int | None = Field(description="Kilometraje actual.", examples=[45000])