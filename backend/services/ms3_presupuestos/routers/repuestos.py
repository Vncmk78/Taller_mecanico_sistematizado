"""Endpoints de repuestos (MS3, RF-13 inventario y RF-14 alerta de stock bajo).

    GET    /repuestos?proveedor_id=&q=&bajo_umbral=&desde=&limite=   listar / buscar
    GET    /repuestos/{repuesto_id}           detalle con umbral efectivo
    POST   /repuestos                         alta con stock inicial (Administrador)
    PATCH  /repuestos/{repuesto_id}           nombre, proveedor, umbral (Administrador)
    DELETE /repuestos/{repuesto_id}           solo si nunca se usó (Administrador)

`bajo_umbral=true` lista los repuestos con stock < umbral efectivo (el
particular o, si no tiene, el general vigente): la alerta de stock bajo.
El stock no se edita aquí: cambia con movimientos de inventario.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response, status

from services.ms3_presupuestos.dependencies import (
    obtener_unidad_de_trabajo,
    requerir_roles,
)
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.repositorios import LIMITE_MAXIMO
from services.ms3_presupuestos.schemas.catalogo import (
    PaginaRepuestos,
    RepuestoActualizar,
    RepuestoCrear,
    RepuestoSalida,
)
from services.ms3_presupuestos.services import catalogo as casos
from shared.auth import NombreRol, PrincipalAutenticado

router = APIRouter(prefix="/repuestos", tags=["repuestos"])

_lectura = requerir_roles(NombreRol.MECANICO, NombreRol.ADMINISTRADOR)
_escritura = requerir_roles(NombreRol.ADMINISTRADOR)

_401 = {status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente, inválido o expirado"}}
_403 = {status.HTTP_403_FORBIDDEN: {"description": "Rol no permitido"}}
_404 = {status.HTTP_404_NOT_FOUND: {"description": "Repuesto o proveedor inexistente"}}
_409 = {status.HTTP_409_CONFLICT: {"description": "Nombre repetido en el proveedor o repuesto con historial"}}
_422 = {422: {"description": "Datos inválidos"}}

IdRepuesto = Path(gt=0, description="repuesto_id")


@router.get("", response_model=PaginaRepuestos, summary="Listar o buscar repuestos",
            responses={**_401, **_403}, dependencies=[Depends(_lectura)])
def listar(
    proveedor_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None, max_length=120, description="Texto en el nombre"),
    bajo_umbral: bool = Query(default=False, description="Solo los que están bajo su umbral"),
    desde: int = Query(default=0, ge=0),
    limite: int = Query(default=50, ge=1, le=LIMITE_MAXIMO),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> PaginaRepuestos:
    total, general, repuestos = casos.listar_repuestos(
        uow, proveedor_id=proveedor_id, texto=q, solo_bajo_umbral=bajo_umbral,
        desde=desde, limite=limite)
    return PaginaRepuestos(total=total, desde=desde, limite=limite, umbral_general=general,
                           repuestos=[casos.a_repuesto(r, general) for r in repuestos])


@router.get("/{repuesto_id}", response_model=RepuestoSalida, summary="Detalle de un repuesto",
            responses={**_401, **_403, **_404}, dependencies=[Depends(_lectura)])
def detalle(repuesto_id: int = IdRepuesto,
            uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)) -> RepuestoSalida:
    return casos.a_repuesto(uow.repuestos.obtener_o_error(repuesto_id), casos.umbral_general(uow))


@router.post("", response_model=RepuestoSalida, status_code=status.HTTP_201_CREATED,
             summary="Registrar un repuesto (con stock inicial respaldado por un ingreso)",
             responses={**_401, **_403, **_404, **_409, **_422})
def crear(body: RepuestoCrear,
          uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
          principal: PrincipalAutenticado = Depends(_escritura)) -> RepuestoSalida:
    repuesto = casos.crear_repuesto(uow, body, administrador_id=principal.usuario_id)
    return casos.a_repuesto(repuesto, casos.umbral_general(uow))


@router.patch("/{repuesto_id}", response_model=RepuestoSalida,
              summary="Modificar nombre, proveedor o umbral particular (queda en el historial)",
              responses={**_401, **_403, **_404, **_409, **_422})
def actualizar(body: RepuestoActualizar, repuesto_id: int = IdRepuesto,
               uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
               principal: PrincipalAutenticado = Depends(_escritura)) -> RepuestoSalida:
    repuesto = casos.actualizar_repuesto(uow, repuesto_id, body,
                                         administrador_id=principal.usuario_id)
    return casos.a_repuesto(repuesto, casos.umbral_general(uow))


@router.delete("/{repuesto_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Eliminar un repuesto que nunca se usó",
               responses={**_401, **_403, **_404, **_409}, dependencies=[Depends(_escritura)])
def eliminar(repuesto_id: int = IdRepuesto,
             uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)) -> Response:
    casos.eliminar_repuesto(uow, repuesto_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
