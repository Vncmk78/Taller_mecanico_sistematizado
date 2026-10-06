"""Endpoints de presupuestos (MS3).

    POST /presupuestos                                         crear (versión 1 en borrador)
    GET  /presupuestos?orden_id=&desde=&limite=                listar / buscar por orden
    GET  /presupuestos/{presupuesto_id}                        detalle con sus versiones
    GET  /presupuestos/{presupuesto_id}/versiones/{n}          una versión
    PUT  /presupuestos/{presupuesto_id}/versiones/{n}/items    reemplazar ítems (solo borrador)
    POST /presupuestos/{presupuesto_id}/versiones/{n}/envio    enviar al cliente (Administrador)
    POST /presupuestos/{presupuesto_id}/versiones/{n}/decision aprobar / rechazar (Cliente dueño)

Acceso (§4.3):
- Mecánico y Administrador: crean, consultan y editan borradores.
- Administrador: revisa precios y envía.
- Cliente: solo presupuestos de SUS órdenes (MS3 lo confirma con MS2
  reenviando su JWT) y solo versiones ya enviadas; decide sobre la última.

Errores: 404 recurso inexistente o ajeno, 409 conflicto de estado de la versión,
422 datos o regla inválida, 503 MS2 no disponible para validar la orden.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from services.ms3_presupuestos.dependencies import (
    obtener_principal_actual,
    obtener_token_bearer,
    obtener_unidad_de_trabajo,
    requerir_roles,
)
from services.ms3_presupuestos.integracion_ms2 import (
    OrdenNoVisible,
    VerificadorOrdenes,
    obtener_verificador_ordenes,
)
from services.ms3_presupuestos.persistencia import RecursoNoEncontrado, UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.repositorios import LIMITE_MAXIMO
from services.ms3_presupuestos.schemas.presupuesto import (
    DecisionEntrada,
    ItemsVersion,
    PaginaPresupuestos,
    PresupuestoCrear,
    PresupuestoDetalle,
    ResultadoOperacion,
    VersionDetalle,
)
from services.ms3_presupuestos.services import presupuestos as casos
from shared.auth import NombreRol, PrincipalAutenticado

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])

_ROLES_PERSONAL = frozenset({NombreRol.MECANICO, NombreRol.ADMINISTRADOR})
_personal_del_taller = requerir_roles(NombreRol.MECANICO, NombreRol.ADMINISTRADOR)
_solo_administrador = requerir_roles(NombreRol.ADMINISTRADOR)
_solo_cliente = requerir_roles(NombreRol.CLIENTE)
_cualquier_rol = requerir_roles(NombreRol.CLIENTE, NombreRol.MECANICO, NombreRol.ADMINISTRADOR)

_401 = {status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente, inválido o expirado"}}
_403_PERSONAL = {status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Mecánico o Administrador"}}
_NO_EXISTE = {status.HTTP_404_NOT_FOUND: {"description": "Presupuesto o versión inexistente (o ajeno)"}}
_503 = {status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "MS2 no disponible para validar la orden"}}
_ERRORES_COMUNES = {**_401, **_403_PERSONAL}

IdPresupuesto = Path(gt=0, description="presupuesto_id")
NumeroVersion = Path(ge=1, description="Número de versión (1, 2, 3...)")


def _es_personal(principal: PrincipalAutenticado) -> bool:
    return bool(_ROLES_PERSONAL & principal.roles)


def _exigir_orden_del_cliente(
    orden_id: int, presupuesto_id: int | None, token: str, verificador: VerificadorOrdenes
) -> None:
    """404 si la orden no es del cliente: no se revela si el presupuesto existe."""
    try:
        verificador.verificar_acceso(orden_id, token)
    except OrdenNoVisible as exc:
        recurso = f"Presupuesto {presupuesto_id}" if presupuesto_id else f"Orden {orden_id}"
        raise RecursoNoEncontrado(f"{recurso} no existe") from exc


# ------------------------------------------------------------------ crear --

@router.post(
    "",
    response_model=PresupuestoDetalle,
    status_code=status.HTTP_201_CREATED,
    summary="Crear el presupuesto de una orden (versión 1 en borrador)",
    responses={
        **_ERRORES_COMUNES,
        status.HTTP_409_CONFLICT: {"description": "La orden ya tiene presupuesto"},
        422: {"description": "Ítems inválidos o repuesto inexistente"},
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


# -------------------------------------------------------------- consultas --

@router.get(
    "",
    response_model=PaginaPresupuestos,
    summary="Listar presupuestos (más recientes primero) o buscar el de una orden",
    description="El cliente debe indicar `orden_id` de una orden suya y solo ve versiones enviadas.",
    responses={**_401, **_503, status.HTTP_403_FORBIDDEN: {"description": "Rol no permitido"}},
)
def listar(
    orden_id: int | None = Query(default=None, gt=0, description="Filtra por orden (MS2)"),
    desde: int = Query(default=0, ge=0),
    limite: int = Query(default=50, ge=1, le=LIMITE_MAXIMO),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_cualquier_rol),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorOrdenes = Depends(obtener_verificador_ordenes),
) -> PaginaPresupuestos:
    if _es_personal(principal):
        total, encontrados = casos.listar_presupuestos(
            uow, orden_id=orden_id, desde=desde, limite=limite
        )
        resumenes = [casos.a_resumen(p) for p in encontrados]
        return PaginaPresupuestos(total=total, desde=desde, limite=limite, presupuestos=resumenes)

    if orden_id is None:
        raise HTTPException(
            status_code=422,
            detail="Indique orden_id para consultar el presupuesto de su orden",
        )
    _exigir_orden_del_cliente(orden_id, None, token, verificador)
    _, encontrados = casos.listar_presupuestos(uow, orden_id=orden_id, desde=0, limite=1)
    visibles = [casos.a_resumen(p, solo_enviadas=True)
                for p in encontrados if any(v.enviada for v in p.versiones)]
    return PaginaPresupuestos(total=len(visibles), desde=0, limite=limite, presupuestos=visibles)


@router.get(
    "/{presupuesto_id}",
    response_model=PresupuestoDetalle,
    summary="Detalle de un presupuesto con sus versiones",
    description="El cliente solo ve presupuestos de sus órdenes y solo las versiones enviadas.",
    responses={**_401, **_NO_EXISTE, **_503},
)
def detalle(
    presupuesto_id: int = IdPresupuesto,
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_cualquier_rol),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorOrdenes = Depends(obtener_verificador_ordenes),
) -> PresupuestoDetalle:
    presupuesto = casos.obtener_presupuesto(uow, presupuesto_id)
    if _es_personal(principal):
        return casos.a_detalle(presupuesto)
    _exigir_orden_del_cliente(presupuesto.orden_id, presupuesto_id, token, verificador)
    return casos.a_detalle(presupuesto, solo_enviadas=True)


@router.get(
    "/{presupuesto_id}/versiones/{numero}",
    response_model=VersionDetalle,
    summary="Una versión del presupuesto con sus ítems y decisión",
    responses={**_401, **_NO_EXISTE, **_503},
)
def version(
    presupuesto_id: int = IdPresupuesto,
    numero: int = NumeroVersion,
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_cualquier_rol),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorOrdenes = Depends(obtener_verificador_ordenes),
) -> VersionDetalle:
    if _es_personal(principal):
        return casos.a_version_detalle(casos.obtener_version(uow, presupuesto_id, numero))
    presupuesto = casos.obtener_presupuesto(uow, presupuesto_id)
    _exigir_orden_del_cliente(presupuesto.orden_id, presupuesto_id, token, verificador)
    return casos.a_version_detalle(
        casos.obtener_version(uow, presupuesto_id, numero, solo_enviadas=True)
    )


# --------------------------------------------------------- editar borrador --

@router.put(
    "/{presupuesto_id}/versiones/{numero}/items",
    response_model=VersionDetalle,
    summary="Reemplazar los ítems de una versión en borrador",
    responses={
        **_ERRORES_COMUNES,
        **_NO_EXISTE,
        status.HTTP_409_CONFLICT: {"description": "La versión ya fue enviada (congelada)"},
        422: {"description": "Ítems inválidos o repuesto inexistente"},
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


# ----------------------------------------------- operaciones transaccionales --

@router.post(
    "/{presupuesto_id}/versiones/{numero}/envio",
    response_model=ResultadoOperacion,
    summary="Enviar la versión al cliente (queda congelada)",
    description=(
        "Solo Administrador. La versión debe ser la última, estar en borrador y tener "
        "ítems con precio. `efecto_en_orden` = `esperando_aprobacion` en el primer envío; "
        "`null` si es una modificación posterior a una aprobación."
    ),
    responses={
        **_401,
        **_NO_EXISTE,
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_409_CONFLICT: {"description": "Ya enviada o no es la última versión"},
        422: {"description": "Sin ítems o con ítems sin precio"},
    },
    dependencies=[Depends(_solo_administrador)],
)
def enviar(
    presupuesto_id: int = IdPresupuesto,
    numero: int = NumeroVersion,
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> ResultadoOperacion:
    return casos.enviar_version(uow, presupuesto_id=presupuesto_id, numero=numero)


@router.post(
    "/{presupuesto_id}/versiones/{numero}/decision",
    response_model=ResultadoOperacion,
    status_code=status.HTTP_201_CREATED,
    summary="Aprobar o rechazar la versión enviada (cliente dueño de la orden)",
    description=(
        "Todo rechazo exige `motivo`. Rechazar antes de la primera aprobación cancela el "
        "servicio y exige `confirmar_cancelacion: true` (efecto `cancelado`). Aprobar da "
        "`en_reparacion` o `esperando_repuestos` según el stock. Rechazar una modificación "
        "posterior conserva la aprobación vigente (efecto `null`)."
    ),
    responses={
        **_401,
        **_NO_EXISTE,
        **_503,
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Cliente"},
        status.HTTP_409_CONFLICT: {"description": "No enviada, ya decidida o reemplazada"},
        422: {"description": "Rechazo sin motivo o sin confirmar la cancelación"},
    },
)
def decidir(
    body: DecisionEntrada,
    presupuesto_id: int = IdPresupuesto,
    numero: int = NumeroVersion,
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_solo_cliente),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorOrdenes = Depends(obtener_verificador_ordenes),
) -> ResultadoOperacion:
    presupuesto = casos.obtener_presupuesto(uow, presupuesto_id)
    _exigir_orden_del_cliente(presupuesto.orden_id, presupuesto_id, token, verificador)
    # Una versión en borrador no existe para el cliente.
    casos.obtener_version(uow, presupuesto_id, numero, solo_enviadas=True)
    # decidir_version vuelve a leer con FOR UPDATE (populate_existing): decide
    # sobre el estado confirmado más reciente, no sobre esta lectura previa.
    return casos.decidir_version(
        uow, presupuesto_id=presupuesto_id, numero=numero,
        cliente_usuario_id=principal.usuario_id, decision=body.decision,
        motivo=body.motivo, confirmar_cancelacion=body.confirmar_cancelacion,
    )
