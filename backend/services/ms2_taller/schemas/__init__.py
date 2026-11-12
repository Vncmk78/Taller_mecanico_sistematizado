"""Schemas públicos de la API de MS2."""

from services.ms2_taller.schemas.bitacora import (
    BitacoraCrear,
    BitacoraRespuesta,
    RepuestoBitacoraEntrada,
    RepuestoBitacoraRespuesta,
)
from services.ms2_taller.schemas.orden import (
    AsignacionMecanicoActualizar,
    CapacidadMecanicoActualizar,
    CapacidadMecanicoRespuesta,
    CupoDiarioIngresosActualizar,
    CupoDiarioIngresosRespuesta,
    HistorialEstadoRespuesta,
    OrdenCrear,
    OrdenRespuesta,
    SolicitudCancelacionRespuesta,
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
    "CapacidadMecanicoActualizar",
    "CapacidadMecanicoRespuesta",
    "CupoDiarioIngresosActualizar",
    "CupoDiarioIngresosRespuesta",
    "HistorialEstadoRespuesta",
    "OrdenCrear",
    "OrdenRespuesta",
    "SolicitudCancelacionRespuesta",
    "RepuestoBitacoraEntrada",
    "RepuestoBitacoraRespuesta",
    "VehiculoActualizar",
    "VehiculoCrear",
    "VehiculoRespuesta",
]
