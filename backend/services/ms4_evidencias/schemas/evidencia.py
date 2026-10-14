"""Contratos HTTP de evidencias (MS4): recepción, lectura y descarga.

`DatosRecepcion` es lo que el Gateway reenvía al recibir una evidencia:
metadatos mínimos (la identidad del autor y el `request_id` se resuelven del
JWT y de la cabecera X-Request-ID, no del body). Aplica en la capa de entrada
las reglas 6 y 7 del modelo, antes de tocar la base. `EvidenciaLeida` es lo que
se expone hacia afuera; `clave_objeto` (apunta al objeto en MinIO) y `sha256`
(integridad interna) NO se exponen. `UrlDescarga` es la respuesta del endpoint
de descarga: una URL prefirmada de corta duración, nunca un enlace permanente.
"""
from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.ms4_evidencias.models.evidencia import ContextoEvidencia


class DatosRecepcion(BaseModel):
    """Metadatos de subida que llegan del Gateway.

    Regla 6: `presupuesto_id` solo se envía con contexto `presupuesto` (y no
    puede faltar en ese contexto). Regla 7: en presupuesto la evidencia siempre
    es visible para el cliente, así que `visible_cliente=False` se rechaza.
    """

    model_config = ConfigDict(extra="forbid")

    orden_id: int = Field(gt=0)
    contexto: ContextoEvidencia
    presupuesto_id: int | None = Field(default=None, gt=0)
    visible_cliente: bool | None = None

    @model_validator(mode="after")
    def aplicar_reglas_6_y_7(self) -> Self:
        es_presupuesto = self.contexto is ContextoEvidencia.PRESUPUESTO
        if es_presupuesto and self.presupuesto_id is None:
            raise ValueError("contexto presupuesto exige presupuesto_id")
        if not es_presupuesto and self.presupuesto_id is not None:
            raise ValueError(
                "presupuesto_id solo se envía cuando contexto es presupuesto"
            )
        if es_presupuesto and self.visible_cliente is False:
            raise ValueError(
                "la evidencia del presupuesto siempre es visible para el cliente"
            )
        if es_presupuesto and self.visible_cliente is None:
            self.visible_cliente = True
        return self


class EvidenciaLeida(BaseModel):
    """Evidencia expuesta por la API de consulta (sin `clave_objeto` ni `sha256`).

    El `contexto` y el `tipo_archivo` viajan como strings legibles; la clave del
    objeto y el hash de integridad son internos y no salen del servicio.
    """

    model_config = ConfigDict(from_attributes=True)

    evidencia_id: UUID
    orden_id: int
    presupuesto_id: int | None
    contexto: str
    tipo_archivo: str
    visible_cliente: bool
    estado: str
    nombre_original: str
    content_type: str
    tamano_bytes: int
    creada_en: datetime


class UrlDescarga(BaseModel):
    """URL GET prefirmada de corta duración para descargar una evidencia.

    El `content_type` y el `Content-Disposition` viajan firmados en la URL; el
    navegador no adivina el tipo ni renderiza el archivo (controles 3.3 y 3.4).
    `expira_en` son segundos desde la emisión.
    """

    url: str
    expira_en: int
