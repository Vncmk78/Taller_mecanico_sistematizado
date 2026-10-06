"""Endpoints iniciales de presupuestos (MS3).

    POST /presupuestos                                   crear (versión 1 en borrador)
    GET  /presupuestos?orden_id=&desde=&limite=          listar / buscar por orden
    GET  /presupuestos/{presupuesto_id}                  detalle con todas las versiones
    GET  /presupuestos/{presupuesto_id}/versiones/{n}    una versión
    PUT  /presupuestos/{presupuesto_id}/versiones/{n}/items   reemplazar ítems (solo borrador)

Acceso: Mecánico y Administrador (§4.3: el mecánico propone, el administrador
revisa precios). El cliente consultará y decidirá sobre la versión ENVIADA
cuando MS3 pueda comprobar con MS2 que la orden es suya (tarea siguiente);
hasta entonces recibe 403.

Errores: 404 recurso inexistente, 409 orden con presupuesto o versión ya
enviada, 422 datos inválidos (main.py traduce los errores de persistencia).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from services.ms3_presupuestos.dependencies import obtener_unidad_de_trabajo, requerir_roles
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.repositorios import LIMITE_MAXIMO
from services.ms3_presupuestos.schemas.presupuesto import (
    ItemsVersion,
    PaginaPresupuestos,
    PresupuestoCrear,
    PresupuestoDetalle,
    VersionDetalle,
)
from services.ms3_presupuestos.services import presupuestos as casos
from shared.auth import NombreRol, PrincipalAutenticado

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])

_personal_del_taller = requerir_roles(NombreRol.MECANICO, NombreRol.ADMINISTRADOR)

_ERRORES_COMUNES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente, inválido o expirado"},
    status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Mecánico o Administrador"},
}
_NO_EXISTE = {status.HTTP_404_NOT_FOUND: {"description": "Presupuesto o versión inexistente"}}

IdPresupuesto = Path(gt=0, description="presupuesto_id")
NumeroVersion = Path(ge=1, description="Número de versión (1, 2, 3...)")


@router.post(
    "",
    response_model=PresupuestoDetalle,
    status_code=status.HTTP_201_CREATED,
    summary="Crear el presupuesto de una orden (versión 1 en borrador)",
    responses={
        **_ERRORES_COMUNES,
        status.HTTP_409_CONFLICT: {"description": "La orden ya tiene presupuesto"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Ítems inválidos o repuesto inexistente"},
    },
)
def crear(
    body: PresupuestoCrear,
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_personal_del_taller),
) -> PresupuestoDetalle:
    presupuesto = casos.crear_presupuesto(
        uow, orden_id=body.orden_id, items=body.items, creado_por_id=principal.usuario_id
    )
    return casos.a_detalle(presupuesto)


@router.get(
    "",
    response_model=PaginaPresupuestos,
    summary="Listar presupuestos (más recientes primero) o buscar el de una orden",
    responses=_ERRORES_COMUNES,
    dependencies=[Depends(_personal_del_taller)],
)
def listar(
    orden_id: int | None = Query(default=None, gt=0, description="Filtra por orden (MS2)"),
    desde: int = Query(default=0, ge=0),
    limite: int = Query(default=50, ge=1, le=LIMITE_MAXIMO),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> PaginaPresupuestos:
    total, encontrados = casos.listar_presupuestos(
        uow, orden_id=orden_id, desde=desde, limite=limite
    )
    return PaginaPresupuestos(
        total=total, desde=desde, limite=limite,
        presupuestos=[casos.a_resumen(p) for p in encontrados],
    )


@router.get(
    "/{presupuesto_id}",
    response_model=PresupuestoDetalle,
    summary="Detalle de un presupuesto con todas sus versiones",
    responses={**_ERRORES_COMUNES, **_NO_EXISTE},
    dependencies=[Depends(_personal_del_taller)],
)
def detalle(
    presupuesto_id: int = IdPresupuesto,
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> PresupuestoDetalle:
    return casos.a_detalle(casos.obtener_presupuesto(uow, presupuesto_id))


@router.get(
    "/{presupuesto_id}/versiones/{numero}",
    response_model=VersionDetalle,
    summary="Una versión del presupuesto con sus ítems y decisión",
    responses={**_ERRORES_COMUNES, **_NO_EXISTE},
    dependencies=[Depends(_personal_del_taller)],
)
def version(
    presupuesto_id: int = IdPresupuesto,
    numero: int = NumeroVersion,
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> VersionDetalle:
    return casos.a_version_detalle(casos.obtener_version(uow, presupuesto_id, numero))


@router.put(
    "/{presupuesto_id}/versiones/{numero}/items",
    response_model=VersionDetalle,
    summary="Reemplazar los ítems de una versión en borrador",
    responses={
        **_ERRORES_COMUNES,
        **_NO_EXISTE,
        status.HTTP_409_CONFLICT: {"description": "La versión ya fue enviada (congelada)"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Ítems inválidos o repuesto inexistente"},
    },
    dependencies=[Depends(_personal_del_taller)],
)
def reemplazar_items(
    body: ItemsVersion,
    presupuesto_id: int = IdPresupuesto,
    numero: int = NumeroVersion,
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> VersionDetalle:
    version_editada = casos.reemplazar_items(
        uow, presupuesto_id=presupuesto_id, numero=numero, items=body.items
    )
    return casos.a_version_detalle(version_editada)
