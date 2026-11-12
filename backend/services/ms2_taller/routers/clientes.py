"""Router del perfil Cliente local de MS2.

Cierra el paso que faltaba entre el registro público (MS1) y el uso de
vehículos (MS2): MS1 crea la cuenta y MS2 necesita su propio perfil Cliente
(sistematización §4.1). Sin este paso explícito, el perfil solo se creaba con
el script de semilla.

* ``POST /clientes/perfil`` prepara el perfil del usuario autenticado. Es
  idempotente: repetirlo (o hacerlo en paralelo) deja un único perfil.
* ``GET /clientes/perfil`` solo consulta; nunca crea el perfil.

La identidad sale del JWT; el body no admite ``usuario_id`` ni roles.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from services.ms2_taller.db import get_db
from services.ms2_taller.dependencies import (
    obtener_principal_actual,
    resolver_cliente_actual,
)
from services.ms2_taller.models.cliente import Cliente
from services.ms2_taller.schemas.cliente import (
    PerfilClientePreparar,
    PerfilClienteRespuesta,
)
from services.ms2_taller.services.clientes import (
    PerfilClienteConflictoError,
    PersistenciaClienteError,
    preparar_perfil_cliente,
)
from shared.auth import NombreRol, PrincipalAutenticado
from shared.errores_auth import error_sin_permiso

router_clientes = APIRouter(prefix="/clientes", tags=["clientes"])


@router_clientes.post(
    "/perfil",
    response_model=PerfilClienteRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Preparar el perfil Cliente del usuario autenticado",
    responses={
        status.HTTP_200_OK: {
            "model": PerfilClienteRespuesta,
            "description": "El perfil ya existía; se devuelve sin modificarlo",
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Cliente"},
        status.HTTP_409_CONFLICT: {
            "description": "El perfil ya existe con otro teléfono; no se modificó"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible preparar el perfil; puede reintentarse"
        },
    },
)
def preparar_perfil(
    body: PerfilClientePreparar,
    response: Response,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> Cliente:
    if NombreRol.CLIENTE not in principal.roles:
        raise error_sin_permiso()
    try:
        cliente, creado = preparar_perfil_cliente(
            db, principal.usuario_id, body.telefono
        )
    except PerfilClienteConflictoError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except PersistenciaClienteError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible preparar el perfil de cliente",
        ) from exc
    if not creado:
        response.status_code = status.HTTP_200_OK
    return cliente


@router_clientes.get(
    "/perfil",
    response_model=PerfilClienteRespuesta,
    summary="Consultar el perfil Cliente del usuario autenticado",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Cliente"},
        status.HTTP_404_NOT_FOUND: {
            "description": "El perfil Cliente todavía no fue preparado"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible consultar el perfil"
        },
    },
)
def consultar_perfil(
    cliente: Cliente = Depends(resolver_cliente_actual),
) -> Cliente:
    # Reutiliza la misma resolución que usan los vehículos: consulta sin crear.
    return cliente
