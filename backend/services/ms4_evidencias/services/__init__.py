"""Servicios de dominio del microservicio MS4 (Evidencia Multimedia).

Contiene la lógica que no pertenece a los contratos HTTP: el cliente de
almacenamiento S3/MinIO (almacenamiento.py) y el flujo de recepción/consulta de
evidencias (evidencias.py). Los endpoints delegan acá.
"""
from __future__ import annotations

from services.ms4_evidencias.services.evidencias import EvidenciaInvalidaError

__all__ = ["EvidenciaInvalidaError"]
