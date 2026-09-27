"""Servicios de dominio del microservicio MS4 (Evidencia Multimedia).

Contiene la lógica que no pertenece a los contratos HTTP: el cliente de
almacenamiento S3/MinIO (almacenamiento.py) y, en la siguiente tarea, el cálculo
del sha256 y la confirmación de evidencias. Los endpoints delegan acá.
"""
