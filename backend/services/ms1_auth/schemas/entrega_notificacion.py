"""Contratos públicos: nunca devuelven tokens de dispositivo o credenciales."""

from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class DispositivoRegistrar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr = Field(min_length=20, max_length=4096)
    plataforma: Literal["android", "ios", "web"]


class DispositivoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dispositivo_id: UUID
    plataforma: str
    activo: bool
    creado_en: datetime
    actualizado_en: datetime


class IntentoEntregaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    numero: int
    iniciado_en: datetime
    finalizado_en: datetime | None
    resultado: str
    codigo_error: str | None


class EntregaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entrega_id: int
    canal: Literal["correo", "push"]
    estado: str
    intentos: int
    aceptada_en: datetime | None
    ultimo_error: str | None
    intentos_registrados: list[IntentoEntregaRespuesta]
