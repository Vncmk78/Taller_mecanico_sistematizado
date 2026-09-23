"""Lógica de aplicación del microservicio MS2."""

from services.ms2_taller.services.clientes import (
    ClienteDuplicadoError,
    PersistenciaClienteError,
    asegurar_cliente,
    buscar_cliente_por_usuario_id,
    crear_cliente,
)
from services.ms2_taller.services.ordenes import (
    OrdenNoEncontradaError,
    PersistenciaOrdenError,
    VehiculoNoEncontradoError as VehiculoOrdenNoEncontradoError,
    crear_orden,
    listar_ordenes,
    obtener_orden_visible,
)
from services.ms2_taller.services.vehiculos import (
    PatenteDuplicadaError,
    PersistenciaVehiculoError,
    VehiculoNoEncontradoError,
    actualizar_vehiculo_propio,
    crear_vehiculo,
    listar_vehiculos,
    obtener_vehiculo_propio,
)

__all__ = [
    "ClienteDuplicadoError",
    "OrdenNoEncontradaError",
    "PatenteDuplicadaError",
    "PersistenciaClienteError",
    "PersistenciaOrdenError",
    "PersistenciaVehiculoError",
    "VehiculoNoEncontradoError",
    "VehiculoOrdenNoEncontradoError",
    "actualizar_vehiculo_propio",
    "asegurar_cliente",
    "buscar_cliente_por_usuario_id",
    "crear_cliente",
    "crear_orden",
    "crear_vehiculo",
    "listar_vehiculos",
    "listar_ordenes",
    "obtener_orden_visible",
    "obtener_vehiculo_propio",
]
