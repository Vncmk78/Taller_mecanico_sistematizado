"""Schemas Pydantic del microservicio MS4 (Evidencia Multimedia).

Contratos de entrada (`DatosRecepcion`, reglas 6 y 7 validadas antes de la
base) y de salida (`EvidenciaLeida`, sin `clave_objeto`) de los endpoints de
evidencias. Definidos en la tarea de recepción y consulta.
"""
from __future__ import annotations

from services.ms4_evidencias.schemas.evidencia import DatosRecepcion, EvidenciaLeida

__all__ = ["DatosRecepcion", "EvidenciaLeida"]
