"""Permisos por rol para las evidencias (MS4), funciones puras.

No tocan HTTP ni la base: reciben el `PrincipalAutenticado` (shared.auth) y
devuelven bool. La relación con la matriz de autorización (docs/) es la
siguiente:

- `puede_subir`: solo Mecánico y Administrador suben evidencias (checklist 3.1).
- `es_vista_cliente`: la consulta usa la vista del cliente (los tres filtros
  acumulativos de `docs/modelo-evidencias.md`) solo cuando el rol más amplio
  del principal es `cliente`. Por la regla multirol de unión (matriz §3.1),
  si además tiene Mecánico o Administrador se aplica el alcance más amplio.
- `es_administrador`: el Administrador ve todo, incluidas las eliminadas
  (auditoría, matriz §4.5).

La pertenencia de la orden al solicitante no se decide aquí: la valida MS2 vía
`integracion_ms2.py` (mismo contrato de MS3). Estas funciones solo deciden por rol.
"""
from __future__ import annotations

from shared.auth import NombreRol, PrincipalAutenticado

_PERSONAL = frozenset({NombreRol.MECANICO, NombreRol.ADMINISTRADOR})


def puede_subir(principal: PrincipalAutenticado) -> bool:
    """Un Cliente solo no puede subir; Mecánico y Administrador sí."""
    return bool(_PERSONAL & principal.roles)


def es_administrador(principal: PrincipalAutenticado) -> bool:
    return NombreRol.ADMINISTRADOR in principal.roles


def es_vista_cliente(principal: PrincipalAutenticado) -> bool:
    """True solo si el rol más amplio del principal es `cliente`.

    Un Cliente+Mecánico o Cliente+Administrador cae en el alcance más amplio
    (unión de roles), no en el filtro estricto del cliente.
    """
    return (
        NombreRol.CLIENTE in principal.roles
        and NombreRol.MECANICO not in principal.roles
        and NombreRol.ADMINISTRADOR not in principal.roles
    )


__all__ = ["puede_subir", "es_administrador", "es_vista_cliente"]