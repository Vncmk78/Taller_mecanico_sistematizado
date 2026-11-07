"""Contratos HTTP para preparar y consultar el perfil Cliente local de MS2.

El perfil Cliente de MS2 solo guarda la referencia lógica al usuario de MS1 y
un teléfono de contacto opcional (sistematización §4.1). El nombre y el correo
oficiales siguen en MS1 y no forman parte de estos contratos.

La identidad del usuario NUNCA viaja en el body: MS2 la toma del JWT.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PerfilClientePreparar(BaseModel):
    """Datos opcionales para preparar el perfil local del Cliente autenticado.

    ``extra="forbid"`` rechaza con ``422`` cualquier intento de enviar un
    ``usuario_id``, ``cliente_id`` o rol para preparar el perfil de un tercero.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    # Largo máximo de la columna `cliente.telefono` (String(30)). No se impone
    # un formato porque la documentación no lo define.
    telefono: str | None = Field(default=None, min_length=1, max_length=30)


class PerfilClienteRespuesta(BaseModel):
    """Perfil Cliente local tal como queda guardado en MS2."""

    model_config = ConfigDict(from_attributes=True)

    cliente_id: int
    usuario_id: int
    telefono: str | None
