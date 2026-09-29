"""Lógica de aplicación del microservicio MS3.

Aquí viven las reglas que no dependen de HTTP: crear versiones de
presupuesto, registrar decisiones, mover stock, calcular el umbral efectivo,
etc. Cada función recibe la `Session` y decide cuándo hacer commit/rollback.
Los routers solo traducen HTTP ↔ estas funciones y sus errores a códigos
(404, 409, 422...).

Las reglas críticas de versionado (versión enviada congelada, bloqueo al
aprobar, decisión inmutable) ya las garantiza la base con triggers
(migración 0003_ms3); los services las anticipan para responder con mensajes
claros en vez de errores de base.
"""
