"""Lógica de aplicación del microservicio MS2."""

from services.ms2_taller.services.clientes import (
    ClienteDuplicadoError,
    PersistenciaClienteError,
    asegurar_cliente,
    buscar_cliente_por_usuario_id,
    crear_cliente,
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
    "PatenteDuplicadaError",
    "PersistenciaClienteError",
    "PersistenciaVehiculoError",
    "VehiculoNoEncontradoError",
    "actualizar_vehiculo_propio",
    "asegurar_cliente",
    "buscar_cliente_por_usuario_id",
    "crear_cliente",
    "crear_vehiculo",
    "listar_vehiculos",
    "obtener_vehiculo_propio",
]
