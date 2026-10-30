"""Constructores HTTP de las respuestas `401` y `403` de los microservicios.

Fuente única de verdad de la *forma* de las respuestas de autenticación y
autorización: todas salen con el cuerpo `{"detail": <mensaje>}` de FastAPI y,
en el caso del `401`, con la cabecera `WWW-Authenticate: Bearer` que pide
RFC 9110. Así cualquier fallo de autenticación (token ausente, mal formado,
inválido, expirado o usuario inexistente) responde igual, y cualquier fallo de
autorización responde igual, sin importar el microservicio.

Vive fuera de `shared.auth` —el contrato puro del token— porque construir una
`HTTPException` depende de FastAPI.
"""
from __future__ import annotations

from fastapi import HTTPException, status

# Mensaje único de toda respuesta `401`. No revela la causa del rechazo.
NO_AUTENTICADO = "No autenticado"
# Mensaje único de toda respuesta `403`.
SIN_PERMISO = "No tienes permiso para realizar esta operación"


def error_no_autenticado(detalle: str = NO_AUTENTICADO) -> HTTPException:
    """`401` normalizado, con la cabecera `WWW-Authenticate: Bearer`."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


def error_sin_permiso(detalle: str = SIN_PERMISO) -> HTTPException:
    """`403` normalizado."""

    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detalle)
