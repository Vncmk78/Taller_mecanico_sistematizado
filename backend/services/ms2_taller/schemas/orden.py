"""Contratos HTTP para creación y consulta inicial de órdenes de trabajo."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrdenCrear(BaseModel):
    """Único dato que un administrador puede aportar al crear una orden."""

    model_config = ConfigDict(extra="forbid")

    vehiculo_id: int = Field(gt=0)


class AsignacionMecanicoActualizar(BaseModel):
    """Datos controlables al asignar o reasignar el responsable de una orden."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    mecanico_id: int = Field(gt=0)
    observacion: str | None = Field(default=None, min_length=1)


class OrdenRespuesta(BaseModel):
    """Representación inicial de una orden expuesta por la API de MS2."""

    model_config = ConfigDict(from_attributes=True)

    orden_id: int
    vehiculo_id: int
    ingreso_id: int
    estado_codigo: int
    mecanico_actual_id: int | None
    creado_por_id: int
    creado_en: datetime
    actualizado_en: datetime


class HistorialEstadoRespuesta(BaseModel):
    """Registro de auditoría de un cambio de estado de una orden."""

    model_config = ConfigDict(from_attributes=True)

    historial_id: int
    orden_id: int
    estado_anterior: int | None
    estado_nuevo: int
    actor_usuario_id: int | None
    fecha_hora: datetime
    origen: Literal["usuario", "sistema"]
    observacion: str | None
