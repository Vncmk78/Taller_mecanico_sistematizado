"""Routers HTTP del microservicio MS2."""

from services.ms2_taller.routers.ordenes import router_ordenes
from services.ms2_taller.routers.vehiculos import crear_router_vehiculos

__all__ = ["crear_router_vehiculos", "router_ordenes"]
