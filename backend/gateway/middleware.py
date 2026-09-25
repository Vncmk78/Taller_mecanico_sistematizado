"""Middleware del identificador de solicitud (`X-Request-ID`).

Asigna un `request_id` a cada petición HTTP: respeta el que envía el cliente
si es válido y, si no viene o es inválido, genera un UUID. El identificador
se guarda en `request.state.request_id`, se agrega a la respuesta y el proxy
lo reenvía al microservicio para poder seguir una petición en ambos lados.
"""
from __future__ import annotations

import re
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Válido: letras, números y guiones, hasta 128 caracteres.
_ID_VALIDO = re.compile(r"^[A-Za-z0-9-]{1,128}$")


class RequestIdMiddleware:
    """Agrega `X-Request-ID` a las respuestas y al estado de la solicitud."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._extraer_o_generar(scope)
        scope.setdefault("state", {})["request_id"] = request_id

        async def enviar_con_id(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start" and not self._ya_tiene_id(
                mensaje
            ):
                mensaje["headers"] = [
                    *mensaje.get("headers", []),
                    (b"x-request-id", request_id.encode("latin-1")),
                ]
            await send(mensaje)

        await self.app(scope, receive, enviar_con_id)

    @staticmethod
    def _ya_tiene_id(mensaje: Message) -> bool:
        for clave, _ in mensaje.get("headers", []):
            if clave.lower() == b"x-request-id":
                return True
        return False

    @staticmethod
    def _extraer_o_generar(scope: Scope) -> str:
        for nombre, valor in scope.get("headers", []):
            if nombre.lower() == b"x-request-id":
                texto = valor.decode("latin-1")
                if _ID_VALIDO.fullmatch(texto):
                    return texto
                break
        return str(uuid.uuid4())