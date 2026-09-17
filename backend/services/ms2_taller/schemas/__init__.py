"""Schemas públicos de la API de MS2."""

from services.ms2_taller.schemas.vehiculo import (
    VehiculoActualizar,
    VehiculoCrear,
    VehiculoRespuesta,
)

__all__ = ["VehiculoActualizar", "VehiculoCrear", "VehiculoRespuesta"]
