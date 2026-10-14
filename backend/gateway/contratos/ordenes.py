"""Copias de los contratos HTTP de MS2 (Órdenes) para la documentación.

La Gateway no importa código de los microservicios: mantiene sus propias
copias para publicar `/docs` aunque MS2 no esté levantado. Las pruebas de
OpenAPI comparan sus campos y obligatoriedad con los esquemas reales de MS2.
"""
from __future__ import annotations

from datetime import datetime
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
    "observacion": "Inicia evaluación técnica",
}

_EJEMPLO_ENTREGA: dict[str, object] = {"observacion": "Entregado al cliente"}

_EJEMPLO_CANCELACION_CLIENTE: dict[str, object] = {
    "motivo": "El cliente ya no desea el servicio"
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
        examples=[6],
    )
    observacion: str | None = Field(
        default=None,
        min_length=1,
        description="Obligatoria al pasar a Cancelado; opcional en los demás destinos.",
        examples=["Inicia evaluación técnica"],
    )


class EntregaSolicitud(BaseModel):
    """Datos controlables al registrar la entrega física de una orden."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_ENTREGA]},
    )

    observacion: str | None = Field(
        default=None,
        min_length=1,
        description="Comentario opcional registrado con la entrega.",
        examples=["Entregado al cliente"],
    )


class CancelacionClienteSolicitud(BaseModel):
    """Motivo obligatorio con el que el cliente cancela su orden."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_CANCELACION_CLIENTE]},
    )

    motivo: str = Field(
        min_length=1,
        description="Motivo de la cancelación; no puede estar vacío.",
        examples=["El cliente ya no desea el servicio"],
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


_EJEMPLO_REPUESTO_BITACORA: dict[str, object] = {
    "nombre": "Pastillas de freno",
    "cantidad": 2,
}

_EJEMPLO_BITACORA_CREAR: dict[str, object] = {
    "tipo": "accion",
    "descripcion": "Se reemplazaron las pastillas delanteras",
    "repuestos": [_EJEMPLO_REPUESTO_BITACORA],
}

_EJEMPLO_BITACORA: dict[str, object] = {
    "bitacora_id": 77,
    "orden_id": 31,
    "autor_usuario_id": 50,
    "tipo": "accion",
    "descripcion": "Se reemplazaron las pastillas delanteras",
    "creado_en": "2026-09-28T12:15:00-03:00",
    "repuestos": [_EJEMPLO_REPUESTO_BITACORA],
}


class RepuestoBitacoraEntrada(BaseModel):
    """Repuesto utilizado en una acción, indicado por nombre y cantidad."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_REPUESTO_BITACORA]},
    )

    nombre: str = Field(
        min_length=1,
        max_length=120,
        description=(
            "Nombre libre del repuesto. La bitácora no referencia el catálogo "
            "de MS3: las bases están aisladas."
        ),
        examples=["Pastillas de freno"],
    )
    cantidad: int = Field(
        gt=0,
        description="Unidades utilizadas; debe ser un entero positivo.",
        examples=[2],
    )


class BitacoraCrear(BaseModel):
    """Datos que el mecánico aporta al registrar una entrada de la bitácora."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"examples": [_EJEMPLO_BITACORA_CREAR]},
    )

    tipo: Literal["observacion", "accion"] = Field(
        description=(
            "Tipo de entrada: 'observacion' es una nota libre y 'accion' un "
            "trabajo realizado que puede declarar repuestos."
        ),
        examples=["accion"],
    )
    descripcion: str = Field(
        min_length=1,
        description="Texto de la observación o de la acción realizada.",
        examples=["Se reemplazaron las pastillas delanteras"],
    )
    repuestos: list[RepuestoBitacoraEntrada] = Field(
        default_factory=list,
        max_length=50,
        description="Repuestos utilizados; solo válido cuando tipo es 'accion'.",
    )


class RepuestoBitacoraRespuesta(BaseModel):
    """Repuesto utilizado en una acción tal como lo devuelve MS2."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EJEMPLO_REPUESTO_BITACORA]})

    nombre: str = Field(description="Nombre libre del repuesto.", examples=["Pastillas de freno"])
    cantidad: int = Field(description="Unidades utilizadas.", examples=[2])


class BitacoraRespuesta(BaseModel):
    """Entrada de la bitácora de trabajo de una orden expuesta por MS2."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EJEMPLO_BITACORA]})

    bitacora_id: int = Field(
        description="Identificador de la entrada de la bitácora.", examples=[77]
    )
    orden_id: int = Field(description="Orden a la que pertenece.", examples=[31])
    autor_usuario_id: int = Field(
        description="Referencia lógica al usuario de MS1 que registró la entrada.",
        examples=[50],
    )
    tipo: Literal["observacion", "accion"] = Field(
        description="Tipo de entrada: 'observacion' o 'accion'.",
        examples=["accion"],
    )
    descripcion: str = Field(
        description="Texto de la observación o de la acción realizada.",
        examples=["Se reemplazaron las pastillas delanteras"],
    )
    creado_en: datetime = Field(
        description="Fecha y hora de creación, generada por la base."
    )
    repuestos: list[RepuestoBitacoraRespuesta] = Field(
        default_factory=list,
        description="Repuestos utilizados en la acción; vacío en una observación.",
    )
