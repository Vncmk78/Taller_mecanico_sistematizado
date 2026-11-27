"""Paquete de microservicios: solo agrupa los submódulos, sin arrancar ninguno.

La aplicación de MS4 vive en ``services.ms4_evidencias.main``. Este archivo no
debe importar ``services.ms4_evidencias.config`` ni crear ``app``: Python lo
ejecuta al importar cualquier ``services.msN_...`` (MS1, MS2 y MS3), por lo que
hacerlo exigiría ``MS4_JWT_SECRET_KEY`` en esos contenedores y los dejaría en
CrashLoopBackOff (despliegue ``sha-181e65d``).
"""
from __future__ import annotations
