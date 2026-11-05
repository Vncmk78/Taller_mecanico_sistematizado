"""Consulta a MS1 si el destino de una asignación es un mecánico válido (§4.3).

La matriz de autorización exige que `mecanico_id` se valide en el servidor:
sin esto, un administrador puede asignar órdenes a un usuario inexistente,
inactivo o sin el rol `mecanico`. Para decidirlo, MS2 llama a
`GET {MS1_URL}/auth/usuarios/{usuario_id}` **con el MISMO JWT** del
administrador que asigna (la ruta de MS1 es exclusiva de ese rol):

    200 con `is_active: true` y `mecanico` en `roles` → destino válido
    200 sin el rol o con `is_active: false`          → UsuarioMecanicoInvalido
    404                                              → UsuarioNoEncontrado
    otro estado / sin conexión / timeout             → ServicioUsuariosNoDisponible

`VerificadorUsuarios` es el puerto; los routers lo reciben por dependencia,
así las pruebas lo reemplazan sin levantar MS1.
"""
from __future__ import annotations

from typing import Protocol

import httpx

from services.ms2_taller.config import settings
from shared.auth import NombreRol


class UsuarioNoEncontrado(Exception):
    """El usuario indicado como destino no existe en MS1."""


class UsuarioMecanicoInvalido(Exception):
    """El usuario existe, pero está inactivo o carece del rol `mecanico`."""


class ServicioUsuariosNoDisponible(Exception):
    """MS1 no respondió de forma utilizable; no se puede validar el destino."""


class VerificadorUsuarios(Protocol):
    def verificar_mecanico(self, usuario_id: int, token: str) -> None:
        """Cada error se comunica lanzando una de las excepciones de arriba."""


class VerificadorUsuariosHttp:
    def __init__(self, url_base: str, timeout: float) -> None:
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout

    def verificar_mecanico(self, usuario_id: int, token: str) -> None:
        try:
            respuesta = httpx.get(
                f"{self.url_base}/auth/usuarios/{usuario_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ServicioUsuariosNoDisponible(
                "No fue posible consultar MS1"
            ) from exc

        if respuesta.status_code == 404:
            raise UsuarioNoEncontrado(
                f"El usuario {usuario_id} no existe"
            )
        if respuesta.status_code != 200:
            raise ServicioUsuariosNoDisponible(
                "MS1 no devolvió un usuario utilizable"
            )

        try:
            datos = respuesta.json()
            roles = datos["roles"]
            activo = datos["is_active"]
        except ValueError as exc:
            raise ServicioUsuariosNoDisponible(
                "Respuesta inválida de MS1"
            ) from exc
        es_mecanico = isinstance(roles, list) and NombreRol.MECANICO.value in roles
        if not es_mecanico or activo is not True:
            raise UsuarioMecanicoInvalido(
                "El usuario indicado no es un mecánico disponible"
            )


def obtener_verificador_usuarios() -> VerificadorUsuarios:
    return VerificadorUsuariosHttp(settings.MS1_URL, settings.MS1_TIMEOUT_SEGUNDOS)
