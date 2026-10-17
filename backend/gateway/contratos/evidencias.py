"""Copias de los contratos HTTP de MS4 (Evidencia Multimedia) para la documentación.

La Gateway no importa código de los microservicios: mantiene sus propias
copias para que `/docs` funcione sin depender de MS4. El test de contrato de
`tests/test_gateway_openapi.py` las compara con los esquemas reales de MS4
(`services/ms4_evidencias/schemas/evidencia.py`).

La subida es `multipart/form-data` (archivo + campos de formulario), por eso
`EvidenciaSubida` describe el formulario y no un body JSON.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_EVIDENCIA_ID = "3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f"

_EJEMPLO_EVIDENCIA: dict[str, object] = {
    "evidencia_id": _EVIDENCIA_ID,
    "orden_id": 31,
    "presupuesto_id": None,
    "contexto": "diagnostico",
    "tipo_archivo": "foto",
    "visible_cliente": False,
    "estado": "confirmada",
    "nombre_original": "frenos delanteros.jpg",
    "content_type": "image/jpeg",
    "tamano_bytes": 482133,
    "creada_en": "2026-10-07T10:15:00-03:00",
}

_EJEMPLO_URL: dict[str, object] = {
    "url": (
        "https://almacenamiento.taller.example/evidencias/ordenes/31/"
        "3f2b8c1e5d4a4e6b9c7d1a2b3c4d5e6f.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256"
        "&X-Amz-Expires=300&X-Amz-Signature=..."
    ),
    "expira_en": 300,
}


# Etapa de la orden en la que se adjunta la evidencia (enum de MS4, en línea
# para no publicar un esquema extra en `components`).
ContextoEvidencia = Literal["diagnostico", "presupuesto", "reparacion", "resultado_final"]


class EvidenciaSubida(BaseModel):
    """Formulario `multipart/form-data` de `POST /api/evidencias`.

    Solo Mecánico (de una orden que atiende) o Administrador. Fotos de hasta
    10 MB por esta vía; el body completo no puede superar 12 MiB en la Gateway.
    """

    model_config = ConfigDict(extra="forbid")

    archivo: bytes = Field(
        description=(
            "Foto o video (`image/*` o `video/*`). El tipo y la extensión los "
            "decide el servidor a partir del Content-Type de la parte."
        ),
        json_schema_extra={"format": "binary"},
    )
    orden_id: int = Field(gt=0, description="Orden de trabajo (MS2).", examples=[31])
    contexto: ContextoEvidencia = Field(
        description=(
            "`presupuesto` exige `presupuesto_id` y siempre es visible para el "
            "cliente; el resto no admite `presupuesto_id`."
        )
    )
    presupuesto_id: int | None = Field(
        default=None, gt=0, description="Solo con contexto `presupuesto`."
    )
    visible_cliente: bool | None = Field(
        default=None,
        description=(
            "Si no se envía rige el valor por contexto: diagnóstico y reparación "
            "ocultas; presupuesto y resultado final visibles."
        ),
    )


class EvidenciaRespuesta(BaseModel):
    """Evidencia tal como la publica MS4 (sin clave del objeto ni hash)."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EJEMPLO_EVIDENCIA]})

    evidencia_id: UUID
    orden_id: int
    presupuesto_id: int | None
    contexto: str = Field(
        description="diagnostico, presupuesto, reparacion o resultado_final."
    )
    tipo_archivo: str = Field(description="foto o video.")
    visible_cliente: bool
    estado: str = Field(description="pendiente, confirmada o anulada.")
    nombre_original: str = Field(
        description="Nombre del archivo ya limpio (sin rutas); solo para mostrar."
    )
    content_type: str
    tamano_bytes: int
    creada_en: datetime


class UrlDescargaRespuesta(BaseModel):
    """URL prefirmada de corta duración para descargar una evidencia."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EJEMPLO_URL]})

    url: str = Field(
        description=(
            "URL GET firmada del almacenamiento. Fuerza el Content-Type validado "
            "y `Content-Disposition: attachment`. No se guarda ni se cachea: se "
            "pide una nueva cada vez."
        )
    )
    expira_en: int = Field(description="Segundos de vigencia desde la emisión.")
