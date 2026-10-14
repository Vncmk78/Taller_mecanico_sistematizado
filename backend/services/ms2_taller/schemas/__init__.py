"""Schemas públicos de la API de MS2."""

from services.ms2_taller.schemas.bitacora import (
    BitacoraCrear,
    BitacoraRespuesta,
    RepuestoBitacoraEntrada,
    RepuestoBitacoraRespuesta,
)
from services.ms2_taller.schemas.orden import (
    AsignacionMecanicoActualizar,
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
    "BitacoraCrear",
    "BitacoraRespuesta",
    "HistorialEstadoRespuesta",
    "OrdenCrear",
    "OrdenRespuesta",
    "RepuestoBitacoraEntrada",
    "RepuestoBitacoraRespuesta",
    "VehiculoActualizar",
    "VehiculoCrear",
    "VehiculoRespuesta",
]
