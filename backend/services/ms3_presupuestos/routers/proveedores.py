"""Endpoints de proveedores (MS3, RF-15: distribuidores de repuestos).

    GET    /proveedores?q=&con_repuestos=&desde=&limite=   listar / buscar (nombre o contacto)
    GET    /proveedores/{proveedor_id}        detalle con sus repuestos
    POST   /proveedores                       crear            (Administrador)
    PATCH  /proveedores/{proveedor_id}        modificar        (Administrador)
    DELETE /proveedores/{proveedor_id}        eliminar si no tiene repuestos (Administrador)

Lectura: Mecánico y Administrador (el mecánico elige repuestos al presupuestar).
El cliente ve el proveedor de cada repuesto dentro de su presupuesto (§4.3),
no el catálogo completo.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response, status

from services.ms3_presupuestos.dependencies import obtener_unidad_de_trabajo, requerir_roles
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.repositorios import LIMITE_MAXIMO
from services.ms3_presupuestos.schemas.catalogo import (
    PaginaProveedores,
    ProveedorActualizar,
    ProveedorCrear,
    ProveedorDetalle,
    ProveedorSalida,
)
from services.ms3_presupuestos.services import catalogo as casos
from shared.auth import NombreRol

router = APIRouter(prefix="/proveedores", tags=["proveedores"])

_lectura = requerir_roles(NombreRol.MECANICO, NombreRol.ADMINISTRADOR)
_escritura = requerir_roles(NombreRol.ADMINISTRADOR)

_401 = {status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente, inválido o expirado"}}
_403 = {status.HTTP_403_FORBIDDEN: {"description": "Rol no permitido"}}
_404 = {status.HTTP_404_NOT_FOUND: {"description": "Proveedor inexistente"}}
_409 = {status.HTTP_409_CONFLICT: {"description": "Nombre repetido o proveedor con repuestos"}}
_422 = {422: {"description": "Datos inválidos"}}

IdProveedor = Path(gt=0, description="proveedor_id")


@router.get("", response_model=PaginaProveedores, summary="Listar o buscar proveedores",
            responses={**_401, **_403}, dependencies=[Depends(_lectura)])
def listar(
    q: str | None = Query(default=None, max_length=120,
                          description="Texto en nombre o contacto (sin distinguir mayúsculas ni tildes)"),
    con_repuestos: bool | None = Query(default=None,
                                       description="true: solo con repuestos · false: sin repuestos"),
    desde: int = Query(default=0, ge=0),
    limite: int = Query(default=50, ge=1, le=LIMITE_MAXIMO),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> PaginaProveedores:
    total, proveedores = casos.listar_proveedores(uow, texto=q, con_repuestos=con_repuestos,
                                                  desde=desde, limite=limite)
    return PaginaProveedores(total=total, desde=desde, limite=limite,
                             proveedores=[casos.a_proveedor(p) for p in proveedores])


@router.get("/{proveedor_id}", response_model=ProveedorDetalle,
            summary="Detalle del proveedor con sus repuestos",
            responses={**_401, **_403, **_404}, dependencies=[Depends(_lectura)])
def detalle(proveedor_id: int = IdProveedor,
            uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)) -> ProveedorDetalle:
    proveedor = uow.proveedores.obtener_o_error(proveedor_id)
    return casos.a_proveedor_detalle(proveedor, casos.umbral_general(uow))


@router.post("", response_model=ProveedorSalida, status_code=status.HTTP_201_CREATED,
             summary="Registrar un proveedor", responses={**_401, **_403, **_409, **_422},
             dependencies=[Depends(_escritura)])
def crear(body: ProveedorCrear,
          uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)) -> ProveedorSalida:
    return casos.a_proveedor(casos.crear_proveedor(uow, nombre=body.nombre, contacto=body.contacto))


@router.patch("/{proveedor_id}", response_model=ProveedorSalida,
              summary="Modificar nombre y/o contacto",
              responses={**_401, **_403, **_404, **_409, **_422},
              dependencies=[Depends(_escritura)])
def actualizar(body: ProveedorActualizar, proveedor_id: int = IdProveedor,
               uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)) -> ProveedorSalida:
    return casos.a_proveedor(casos.actualizar_proveedor(uow, proveedor_id, body))


@router.delete("/{proveedor_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Eliminar un proveedor sin repuestos",
               responses={**_401, **_403, **_404, **_409}, dependencies=[Depends(_escritura)])
def eliminar(proveedor_id: int = IdProveedor,
             uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)) -> Response:
    casos.eliminar_proveedor(uow, proveedor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
