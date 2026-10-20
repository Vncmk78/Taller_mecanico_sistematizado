"""Schemas públicos de la API de MS2."""

from services.ms2_taller.schemas.orden import (
    AsignacionMecanicoActualizar,
    CapacidadMecanicoActualizar,
    CapacidadMecanicoRespuesta,
    HistorialEstadoRespuesta,
    OrdenCrear,
    OrdenRespuesta,
)
from services.ms2_taller.schemas.vehiculo import (
    VehiculoActualizar,
    VehiculoCrear,
    VehiculoRespuesta,
)

__all__ = [
    "AsignacionMecanicoActualizar",
    "CapacidadMecanicoActualizar",
    "CapacidadMecanicoRespuesta",
    "HistorialEstadoRespuesta",
    "OrdenCrear",
    "OrdenRespuesta",
    "VehiculoActualizar",
    "VehiculoCrear",
    "VehiculoRespuesta",
]
