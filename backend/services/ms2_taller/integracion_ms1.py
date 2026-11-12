"""Valida el destinatario de una asignación por la API de MS1, sin compartir BD."""
from __future__ import annotations

from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from services.ms2_taller.config import settings
from shared.auth import NombreRol


class MecanicoNoValidoError(Exception):
    """El usuario no existe, está inactivo o no tiene rol Mecánico."""


class ServicioUsuariosNoDisponibleError(Exception):
    """No fue posible confirmar los datos oficiales del usuario."""


class _UsuarioParaAsignacion(BaseModel):
    model_config = ConfigDict(strict=True)

    id: int = Field(gt=0)
    is_active: bool
    roles: list[str]


class VerificadorMecanicos(Protocol):
    def verificar(self, mecanico_id: int, token: str) -> None: ...


class VerificadorMecanicosHttp:
    def __init__(self, url_base: str, timeout: float) -> None:
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout

    def verificar(self, mecanico_id: int, token: str) -> None:
        try:
            respuesta = httpx.get(
                f"{self.url_base}/auth/usuarios/{mecanico_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ServicioUsuariosNoDisponibleError() from exc
        if respuesta.status_code == 404:
            raise MecanicoNoValidoError()
        if respuesta.status_code != 200:
            raise ServicioUsuariosNoDisponibleError()
        try:
            usuario = _UsuarioParaAsignacion.model_validate(respuesta.json())
        except ValueError as exc:
            raise ServicioUsuariosNoDisponibleError() from exc
        if usuario.id != mecanico_id:
            raise ServicioUsuariosNoDisponibleError()
        if not usuario.is_active or NombreRol.MECANICO.value not in usuario.roles:
            raise MecanicoNoValidoError()


def obtener_verificador_mecanicos() -> VerificadorMecanicos:
    return VerificadorMecanicosHttp(settings.MS1_URL, settings.MS1_TIMEOUT_SEGUNDOS)
