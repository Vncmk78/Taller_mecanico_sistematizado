"""Contexto de la solicitud que llega de la Gateway (MS4).

Este módulo es puro: normaliza valores que vienen de cabeceras de la Gateway
sin tocar HTTP. El único campo que se guarda es el `request_id`.

El autor de la evidencia (`autor_usuario_id`) no viene en el body: lo entrega
el endpoint a partir del principal autenticado (`PrincipalAutenticado` de
`shared.auth`). Ese principal expone el id del usuario en el atributo
`usuario_id`, así que el servicio recibe `principal.usuario_id`, no un campo
del cliente. El endpoint que conecte esto llegará en la Semana 6.
"""
from __future__ import annotations

import re

# Cabecera que la Gateway propaga/entrega en cada request (gateway/errores.py).
CABECERA_REQUEST_ID = "X-Request-ID"

# Solo caracteres seguros en logs y en la columna request_id.
_PATRON_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def normalizar_request_id(valor: str | None) -> str | None:
    """Devuelve el request_id si es válido, `None` si no.

    Se acepta solo `[A-Za-z0-9._-]` y como máximo 64 caracteres (tamaño de la
    columna `request_id` del modelo): un valor con espacios, con otros
    caracteres o más largo NO es de la Gateway y se descarta (queda `None`)
    en vez de recortarlo silenciosamente.
    """
    if valor is None:
        return None
    if not valor or len(valor) > 64:
        return None
    if _PATRON_REQUEST_ID.fullmatch(valor) is None:
        return None
    return valor