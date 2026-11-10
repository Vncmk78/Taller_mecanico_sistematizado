"""Copias de los contratos HTTP de MS2 (perfil Cliente) para la documentación.

La Gateway no importa código de los microservicios: mantiene sus propias
copias para que `/docs` funcione sin depender de MS2. El test de contrato de
`tests/test_gateway_openapi.py` las compara con los esquemas reales de MS2.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_EJEMPLO_PREPARAR: dict[str, object] = {"telefono": "+56 9 1234 5678"}

_EJEMPLO_RESPUESTA: dict[str, object] = {
    "cliente_id": 7,
    "usuario_id": 42,
    "telefono": "+56 9 1234 5678",
}


class PerfilClientePreparar(BaseModel):
    """Datos opcionales para preparar el perfil Cliente del usuario del JWT."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_PREPARAR, {}]},
    )

    telefono: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
        description=(
            "Teléfono de contacto opcional. Solo se guarda al crear el perfil; "
            "si el perfil ya existe con otro teléfono responde 409 y no lo "
            "modifica. No se prescribe formato. El body no admite `usuario_id` "
            "ni roles: la identidad sale del JWT."
        ),
        examples=["+56 9 1234 5678"],
    )


class PerfilClienteRespuesta(BaseModel):
    """Perfil Cliente local guardado en MS2 (sin nombre ni correo: están en MS1)."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EJEMPLO_RESPUESTA]})

    cliente_id: int = Field(
        description="Identificador del perfil Cliente en MS2 (`cliente_id` de los vehículos).",
        examples=[7],
    )
    usuario_id: int = Field(
        description="Usuario de MS1 dueño del perfil (el `sub` del JWT).",
        examples=[42],
    )
    telefono: str | None = Field(description="Teléfono de contacto.", examples=["+56 9 1234 5678"])
