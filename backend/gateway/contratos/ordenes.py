"""Copias de los contratos HTTP de MS2 (Órdenes) para la documentación.

La Gateway no importa código de los microservicios: mantiene sus propias
copias para publicar `/docs` aunque MS2 no esté levantado. Las pruebas de
OpenAPI comparan sus campos y obligatoriedad con los esquemas reales de MS2.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

_EJEMPLO_CREAR: dict[str, object] = {"vehiculo_id": 12}

_EJEMPLO_ASIGNAR: dict[str, object] = {
    "mecanico_id": 50,
    "observacion": "Asignación inicial",
}

_EJEMPLO_RESPUESTA: dict[str, object] = {
    "orden_id": 31,
    "vehiculo_id": 12,
    "ingreso_id": 18,
    "estado_codigo": 1,
    "mecanico_actual_id": None,
    "creado_por_id": 99,
    "creado_en": "2026-09-28T10:30:00-03:00",
    "actualizado_en": "2026-09-28T10:30:00-03:00",
}

_EJEMPLO_CAMBIAR_ESTADO: dict[str, object] = {
    "estado_destino": 2,
    "observacion": "Inicia evaluación técnica",
}

_EJEMPLO_HISTORIAL: dict[str, object] = {
    "historial_id": 41,
    "orden_id": 31,
    "estado_anterior": 1,
    "estado_nuevo": 2,
    "actor_usuario_id": 50,
    "origen": "usuario",
    "fecha_hora": "2026-09-28T11:00:00-03:00",
    "observacion": "Inicia evaluación técnica",
}


class OrdenCrear(BaseModel):
    """Dato que un administrador proporciona al crear una orden."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_CREAR]},
    )

    vehiculo_id: int = Field(
        gt=0,
        description="Vehículo registrado en MS2 para el que se crea la orden.",
        examples=[12],
    )


class AsignacionMecanicoActualizar(BaseModel):
    """Datos para asignar o reasignar al responsable actual de una orden."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_ASIGNAR]},
    )

    mecanico_id: int = Field(
        gt=0,
        description=(
            "Referencia lógica al usuario de MS1 que quedará como mecánico "
            "responsable. No es una FK física entre bases."
        ),
        examples=[50],
    )
    observacion: str | None = Field(
        default=None,
        min_length=1,
        description="Motivo u observación opcional de la asignación.",
        examples=["Asignación inicial"],
    )


class OrdenRespuesta(BaseModel):
    """Representación inicial de una orden expuesta por MS2."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EJEMPLO_RESPUESTA]})

    orden_id: int = Field(description="Identificador de la orden.", examples=[31])
    vehiculo_id: int = Field(description="Vehículo atendido.", examples=[12])
    ingreso_id: int = Field(description="Ingreso físico asociado.", examples=[18])
    estado_codigo: int = Field(
        description="Código del estado oficial actual (1 a 8).",
        examples=[1],
    )
    mecanico_actual_id: int | None = Field(
        description=(
            "Referencia lógica al responsable actual en MS1; puede ser nula "
            "mientras la orden está recibida y sin asignación."
        ),
        examples=[50],
    )
    creado_por_id: int = Field(
        description="Referencia lógica al administrador de MS1 que creó la orden.",
        examples=[99],
    )
    creado_en: datetime = Field(description="Fecha y hora de creación de la orden.")
    actualizado_en: datetime = Field(
        description="Fecha y hora de la última actualización de la orden."
    )


class CambioEstadoSolicitud(BaseModel):
    """Datos controlables al solicitar un cambio de estado de una orden."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_CAMBIAR_ESTADO]},
    )

    # Sin tope superior: el catálogo oficial (1 a 8) lo valida el dominio, que
    # es quien conoce los estados y las transiciones permitidas.
    estado_destino: int = Field(
        gt=0,
        description="Código del estado de destino en el catálogo oficial.",
        examples=[2],
    )
    observacion: str | None = Field(
        default=None,
        min_length=1,
        description="Observación opcional del cambio de estado.",
        examples=["Inicia evaluación técnica"],
    )


class HistorialEstadoRespuesta(BaseModel):
    """Registro inmutable de un cambio de estado de una orden."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EJEMPLO_HISTORIAL]})

    historial_id: int = Field(
        description="Identificador del registro de historial.", examples=[41]
    )
    orden_id: int = Field(description="Orden a la que pertenece.", examples=[31])
    estado_anterior: int | None = Field(
        description="Estado de origen; nulo en la transición de creación.",
        examples=[1],
    )
    estado_nuevo: int = Field(
        description="Estado al que pasó la orden.", examples=[2]
    )
    actor_usuario_id: int | None = Field(
        description="Referencia lógica al usuario de MS1 que registró el cambio.",
        examples=[50],
    )
    origen: str = Field(
        description="Origen del registro: 'usuario' o 'sistema'.",
        examples=["usuario"],
    )
    fecha_hora: datetime = Field(
        description="Fecha y hora del cambio, generada por la base."
    )
    observacion: str | None = Field(
        description="Observación opcional registrada con el cambio.",
        examples=["Inicia evaluación técnica"],
    )
