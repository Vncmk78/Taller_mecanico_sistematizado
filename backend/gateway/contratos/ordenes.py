"""Copias de los contratos HTTP de MS2 (Órdenes) para la documentación.

La Gateway no importa código de los microservicios: mantiene sus propias
copias para publicar `/docs` aunque MS2 no esté levantado. Las pruebas de
OpenAPI comparan sus campos y obligatoriedad con los esquemas reales de MS2.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

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
    "estado_destino": 6,
    "observacion": "Trabajo autorizado finalizado",
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


class CapacidadMecanicoActualizar(BaseModel):
    """Límite de órdenes activas que un Administrador configura por mecánico."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"max_ordenes_activas": 5}]},
    )

    max_ordenes_activas: int = Field(
        gt=0,
        strict=True,
        description="Máximo positivo de órdenes asignadas no terminales por mecánico.",
        examples=[5],
    )


class CapacidadMecanicoRespuesta(BaseModel):
    """Configuración vigente e información de mecánicos sobre el nuevo límite."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "max_ordenes_activas": 5,
                    "actualizado_por_id": 99,
                    "actualizado_en": "2026-10-20T10:00:00-03:00",
                    "mecanicos_sobre_limite": [],
                }
            ]
        }
    )

    max_ordenes_activas: int | None = Field(
        description="Nulo hasta que un Administrador configure el límite."
    )
    actualizado_por_id: int | None = Field(
        description="Referencia lógica al Administrador que configuró el valor."
    )
    actualizado_en: datetime = Field(description="Fecha y hora de la configuración.")
    mecanicos_sobre_limite: list[dict[str, int]] = Field(
        description="Mecánicos cuya carga actual supera el máximo recién configurado."
    )


class CupoDiarioIngresosActualizar(BaseModel):
    """Límite de ingresos físicos que un Administrador configura por jornada."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"max_ingresos_diarios": 12}]},
    )

    max_ingresos_diarios: int = Field(
        gt=0,
        strict=True,
        description="Máximo positivo de ingresos físicos en una jornada local.",
        examples=[12],
    )


class CupoDiarioIngresosRespuesta(BaseModel):
    """Límite diario vigente, jornada y número de ingresos registrados."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "max_ingresos_diarios": 12,
                    "actualizado_por_id": 99,
                    "actualizado_en": "2026-10-23T10:00:00-03:00",
                    "jornada_local": "2026-10-23",
                    "ingresos_registrados": 4,
                    "sobre_limite": False,
                }
            ]
        }
    )

    max_ingresos_diarios: int | None = Field(
        description="Nulo hasta que un Administrador configure el límite."
    )
    actualizado_por_id: int | None = Field(
        description="Referencia lógica al Administrador que configuró el valor."
    )
    actualizado_en: datetime
    jornada_local: date
    ingresos_registrados: int = Field(
        description="Ingresos físicos registrados en la jornada local actual."
    )
    sobre_limite: bool = Field(
        description="Indica si el uso actual excede el límite configurado."
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


class HistorialOrdenesVehiculoRespuesta(BaseModel):
    """Página del historial de órdenes visibles de un vehículo."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [_EJEMPLO_RESPUESTA],
                    "total": 1,
                    "limit": 20,
                    "offset": 0,
                }
            ]
        }
    )

    items: list[OrdenRespuesta] = Field(description="Órdenes de la página actual.")
    total: int = Field(description="Cantidad total de órdenes visibles del vehículo.")
    limit: int = Field(description="Máximo de elementos solicitado para la página.")
    offset: int = Field(description="Índice del primer elemento de la página.")


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
        examples=[6],
    )
    observacion: str | None = Field(
        default=None,
        min_length=1,
        description="Obligatoria al pasar a Cancelado; opcional en los demás destinos.",
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
    origen: Literal["usuario", "sistema"] = Field(
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
