"""Endpoints de inventario y stock (MS3, §4.6).

    POST /inventario/movimientos                  registrar movimiento (idempotente por clave)
    GET  /inventario/movimientos?repuesto_id=&orden_id=&tipo=&proveedor_id=&desde=&limite=
    GET  /inventario/stock/{repuesto_id}          stock, comprometido, disponible y alerta
    GET  /inventario/alertas                      repuestos con stock < umbral efectivo
    GET  /inventario/umbral-general               umbral general vigente
    PUT  /inventario/umbral-general               cambiarlo (Administrador; queda en historial)
    GET  /inventario/historial-umbral?repuesto_id=&solo_general=
    POST /inventario/disponibilidad                ¿alcanza el stock para usar estos repuestos?
    GET  /inventario/ordenes/{orden_id}/disponibilidad  ¿alcanza para lo aprobado de la orden?
    POST /inventario/ordenes/{orden_id}/reserva    reservar lo pendiente del presupuesto aprobado
    POST /inventario/ordenes/{orden_id}/consumos   descontar varios repuestos (todo o nada)
    POST /inventario/ordenes/{orden_id}/liberacion liberar todo lo reservado (p. ej. al cancelar)

Stock insuficiente → 409 con `faltantes` (solicitado, disponible, faltan) y no
se aplica nada de la operación.

Acceso: Mecánico y Administrador leen. Ingresos, ajustes y umbral general:
solo Administrador. Compromisos, consumos y liberaciones (siempre de una
orden): Mecánico o Administrador; el mecánico solo sobre las órdenes que
tiene asignadas (MS3 lo confirma con MS2 reenviando su JWT, §4.4). El
cliente no accede (403).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from services.ms3_presupuestos.dependencies import (
    obtener_token_bearer,
    obtener_unidad_de_trabajo,
    requerir_roles,
)
from services.ms3_presupuestos.integracion_ms2 import (
    OrdenNoVisible,
    ServicioOrdenesNoDisponible,
    VerificadorOrdenes,
    obtener_verificador_ordenes,
)
from services.ms3_presupuestos.persistencia import RecursoNoEncontrado, UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.repositorios import LIMITE_MAXIMO
from services.ms3_presupuestos.schemas.inventario import (
    CambioUmbral,
    ConsultaDisponibilidad,
    ConsumoOrden,
    LiberacionOrden,
    MovimientoCrear,
    MovimientoSalida,
    PaginaAlertas,
    PaginaMovimientos,
    RechazoStock,
    ResultadoDisponibilidad,
    ResultadoMovimiento,
    ResultadoOperacionOrden,
    ResultadoReserva,
    StockSalida,
    TipoMovimiento,
    UmbralGeneralEntrada,
    UmbralGeneralSalida,
    TIPOS_CON_ORDEN,
)
from services.ms3_presupuestos.services import disponibilidad
from services.ms3_presupuestos.services import inventario as casos
from services.ms3_presupuestos.services import reservas
from shared.auth import NombreRol, PrincipalAutenticado

router = APIRouter(prefix="/inventario", tags=["inventario"])

_personal = requerir_roles(NombreRol.MECANICO, NombreRol.ADMINISTRADOR)
_administrador = requerir_roles(NombreRol.ADMINISTRADOR)

_401 = {status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente, inválido o expirado"}}
_403 = {status.HTTP_403_FORBIDDEN: {"description": "Rol no permitido"}}
_404 = {status.HTTP_404_NOT_FOUND: {"description": "Repuesto inexistente"}}
_404_REPUESTOS = status.HTTP_404_NOT_FOUND


@router.post(
    "/movimientos",
    response_model=ResultadoMovimiento,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un movimiento de stock",
    description=(
        "Ingreso y ajuste: Administrador. Compromiso, consumo y liberación: Mecánico o "
        "Administrador, siempre con `orden_id`; el mecánico solo sobre órdenes que tiene "
        "asignadas (§4.4). Reenviar la misma `clave_operacion` devuelve el movimiento "
        "original con 200 y `repetido: true` (no se aplica dos veces)."
    ),
    responses={
        **_401, **_403, **_404,
        status.HTTP_404_NOT_FOUND: {"description": "Repuesto u orden inexistente (o no asignada al mecánico)"},
        status.HTTP_200_OK: {"description": "Clave repetida: se devuelve el movimiento original"},
        status.HTTP_409_CONFLICT: {"model": RechazoStock,
                                   "description": "Stock insuficiente (con `faltantes`), liberación "
                                                  "mayor a lo comprometido o clave usada con otros datos"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "MS2 no disponible para validar la orden del mecánico"
        },
        422: {"description": "Datos inválidos"},
    },
)
def registrar(
    body: MovimientoCrear,
    response: Response,
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_personal),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorOrdenes = Depends(obtener_verificador_ordenes),
) -> ResultadoMovimiento:
    if body.tipo in casos.TIPOS_ADMINISTRADOR and NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail=f"Solo el administrador registra un {body.tipo}")
    # §4.4: el mecánico solo mueve stock de las órdenes que tiene asignadas.
    # La validación va antes de tocar stock: nada se registra sin acceso.
    if (
        body.orden_id is not None
        and NombreRol.ADMINISTRADOR not in principal.roles
    ):
        try:
            verificador.verificar_acceso(body.orden_id, token)
        except OrdenNoVisible as exc:
            raise RecursoNoEncontrado(f"Orden {body.orden_id} no existe") from exc
        # ServicioOrdenesNoDisponible viaja al manejador global de MS3 (503).
    resultado = casos.registrar_movimiento(uow, body, usuario_id=principal.usuario_id)
    if resultado.repetido:
        response.status_code = status.HTTP_200_OK
    return resultado


@router.get("/movimientos", response_model=PaginaMovimientos,
            summary="Movimientos (más recientes primero)",
            responses={**_401, **_403}, dependencies=[Depends(_personal)])
def listar_movimientos(
    repuesto_id: int | None = Query(default=None, gt=0),
    orden_id: int | None = Query(default=None, gt=0),
    tipo: TipoMovimiento | None = Query(default=None),
    proveedor_id: int | None = Query(default=None, gt=0,
                                     description="Ingresos entregados por ese proveedor"),
    desde: int = Query(default=0, ge=0),
    limite: int = Query(default=50, ge=1, le=LIMITE_MAXIMO),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> PaginaMovimientos:
    total, movimientos = casos.listar_movimientos(
        uow, repuesto_id=repuesto_id, orden_id=orden_id, tipo=tipo, proveedor_id=proveedor_id,
        desde=desde, limite=limite)
    return PaginaMovimientos(total=total, desde=desde, limite=limite,
                             movimientos=[MovimientoSalida.model_validate(m) for m in movimientos])


@router.get("/stock/{repuesto_id}", response_model=StockSalida,
            summary="Stock físico, comprometido por orden y disponible",
            responses={**_401, **_403, **_404}, dependencies=[Depends(_personal)])
def stock(repuesto_id: int = Path(gt=0),
          uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)) -> StockSalida:
    return casos.estado_stock(uow, uow.repuestos.obtener_o_error(repuesto_id))


@router.get("/alertas", response_model=PaginaAlertas,
            summary="Repuestos con stock bajo su umbral efectivo (los que más faltan primero)",
            responses={**_401, **_403}, dependencies=[Depends(_personal)])
def alertas(uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)) -> PaginaAlertas:
    general, lista = casos.alertas(uow)
    return PaginaAlertas(umbral_general=general, total=len(lista), alertas=lista)


@router.get("/umbral-general", response_model=UmbralGeneralSalida,
            summary="Umbral general vigente (null si aún no se configura)",
            responses={**_401, **_403}, dependencies=[Depends(_personal)])
def ver_umbral_general(uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)) -> UmbralGeneralSalida:
    return casos.obtener_umbral_general(uow)


@router.put("/umbral-general", response_model=UmbralGeneralSalida,
            summary="Configurar el umbral general (queda en el historial)",
            responses={**_401, status.HTTP_403_FORBIDDEN: {"description": "Solo Administrador"},
                       422: {"description": "Valor inválido"}})
def cambiar_umbral_general(
    body: UmbralGeneralEntrada,
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_administrador),
) -> UmbralGeneralSalida:
    return casos.cambiar_umbral_general(uow, valor=body.umbral_general,
                                        administrador_id=principal.usuario_id,
                                        observacion=body.observacion)


@router.get("/historial-umbral", response_model=list[CambioUmbral],
            summary="Cambios de umbral (general y/o de un repuesto), más recientes primero",
            responses={**_401, **_403, **_404}, dependencies=[Depends(_personal)])
def historial_umbral(
    repuesto_id: int | None = Query(default=None, gt=0),
    solo_general: bool = Query(default=False),
    limite: int = Query(default=50, ge=1, le=LIMITE_MAXIMO),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> list[CambioUmbral]:
    return casos.historial_umbral(uow, repuesto_id=repuesto_id, solo_general=solo_general,
                                  limite=limite)


@router.post(
    "/disponibilidad", response_model=ResultadoDisponibilidad,
    summary="Validar si alcanza el stock antes de usar repuestos",
    description=(
        "No mueve stock: responde si cada repuesto alcanza y cuántas unidades faltan. "
        "Con `orden_id` cuenta como disponible lo que esa orden ya reservó y descuenta "
        "lo reservado por otras órdenes."
    ),
    responses={**_401, **_403, _404_REPUESTOS: {"description": "Algún repuesto no existe"},
               422: {"description": "Datos inválidos"}},
    dependencies=[Depends(_personal)],
)
def validar_disponibilidad(
    body: ConsultaDisponibilidad, uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> ResultadoDisponibilidad:
    return disponibilidad.evaluar(
        uow, disponibilidad.requeridos_de_items(body.items), orden_id=body.orden_id)


@router.get(
    "/ordenes/{orden_id}/disponibilidad", response_model=ResultadoDisponibilidad,
    summary="Validar el stock para lo que falta usar del presupuesto aprobado de una orden",
    description=(
        "Requerido = repuestos de la versión aprobada vigente − lo ya consumido por la orden. "
        "Sirve para saber si una orden en 'Esperando repuestos' ya puede continuar."
    ),
    responses={**_401, **_403,
               _404_REPUESTOS: {"description": "La orden no tiene presupuesto"},
               status.HTTP_409_CONFLICT: {"description": "La orden no tiene un presupuesto aprobado"}},
    dependencies=[Depends(_personal)],
)
def disponibilidad_de_orden(
    orden_id: int = Path(gt=0), uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> ResultadoDisponibilidad:
    return disponibilidad.evaluar_orden(uow, orden_id)


_409_STOCK = {status.HTTP_409_CONFLICT: {
    "model": RechazoStock,
    "description": "Stock insuficiente: `faltantes` por repuesto; no se aplicó nada"}}


@router.post(
    "/ordenes/{orden_id}/reserva", response_model=ResultadoReserva,
    summary="Reservar lo que falta usar del presupuesto aprobado (todo o nada)",
    description=(
        "Ajusta la reserva de la orden a lo pendiente de su presupuesto aprobado: reserva lo que "
        "falta y libera lo que sobra. Si algún repuesto no alcanza no reserva nada y responde "
        "`reservado: false` con los faltantes (la orden sigue esperando repuestos)."
    ),
    responses={**_401, **_403, _404_REPUESTOS: {"description": "La orden no tiene presupuesto"},
               status.HTTP_409_CONFLICT: {"description": "La orden no tiene un presupuesto aprobado"}},
)
def reservar(
    orden_id: int = Path(gt=0), uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_personal),
) -> ResultadoReserva:
    return reservas.reservar_presupuesto_aprobado(uow, orden_id, usuario_id=principal.usuario_id)


@router.post(
    "/ordenes/{orden_id}/consumos", response_model=ResultadoOperacionOrden,
    status_code=status.HTTP_201_CREATED,
    summary="Descontar varios repuestos usados en la orden (todo o nada)",
    description=(
        "Usa primero lo reservado por la orden y el resto debe estar libre; nunca toma lo "
        "reservado por otra orden. Reenviar la misma `clave_operacion` devuelve lo ya aplicado "
        "con 200 y `repetido: true`."
    ),
    responses={**_401, **_403, **_409_STOCK,
               _404_REPUESTOS: {"description": "Algún repuesto no existe"},
               status.HTTP_200_OK: {"description": "Clave repetida: no se descontó de nuevo"},
               422: {"description": "Datos inválidos"}},
)
def consumir(
    body: ConsumoOrden, response: Response, orden_id: int = Path(gt=0),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_personal),
) -> ResultadoOperacionOrden:
    resultado = reservas.consumir_para_orden(
        uow, orden_id, disponibilidad.requeridos_de_items(body.items),
        usuario_id=principal.usuario_id, clave_operacion=body.clave_operacion)
    if resultado.repetido:
        response.status_code = status.HTTP_200_OK
    return resultado


@router.post(
    "/ordenes/{orden_id}/liberacion", response_model=ResultadoOperacionOrden,
    summary="Liberar todo lo reservado por la orden (p. ej. al cancelarla)",
    responses={**_401, **_403, 422: {"description": "Datos inválidos"}},
)
def liberar(
    body: LiberacionOrden, orden_id: int = Path(gt=0),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_personal),
) -> ResultadoOperacionOrden:
    return reservas.liberar_orden(uow, orden_id, usuario_id=principal.usuario_id,
                                  clave_operacion=body.clave_operacion)


from services.ms3_presupuestos.dependencies import obtener_token_bearer
from services.ms3_presupuestos.integracion_ms2 import (
    AplicacionDisponibilidadPendienteError, CoordinadorDisponibilidadRepuestos,
    ReservaRepuestosNoAplicableError, obtener_coordinador_disponibilidad_repuestos,
)
from services.ms3_presupuestos.persistencia import ConflictoDeDatos
from services.ms3_presupuestos.schemas.inventario import (
    DisponibilidadRepuestosRespuesta, DisponibilidadRepuestosVerificada,
)
from services.ms3_presupuestos.services.disponibilidad_repuestos import (
    RepuestosInsuficientesError, reservar_repuestos_aprobados,
    revertir_reserva_rechazada, verificar_reserva_confirmada,
)

_solo_administrador = requerir_roles(NombreRol.ADMINISTRADOR)


@router.post(
    "/ordenes/{orden_id}/disponibilidad",
    response_model=DisponibilidadRepuestosRespuesta,
    summary="Reservar stock libre y continuar una orden",
    description=(
        "Solo Administrador. MS3 compara las cantidades enteras del alcance "
        "aprobado con el stock libre (stock físico menos compromisos de otras "
        "órdenes), registra los compromisos de forma idempotente y solicita a "
        "MS2 la transición auditada Esperando repuestos → En reparación."
    ),
    responses={
        401: {"description": "JWT ausente o inválido"},
        403: {"description": "Se requiere rol Administrador"},
        404: {"description": "Presupuesto u orden inexistente"},
        409: {"description": "Stock libre insuficiente o estado incompatible"},
        422: {"description": "Los repuestos deben estar expresados en unidades enteras"},
        503: {"description": "Reserva persistida; aplicación en MS2 pendiente de reintento"},
    },
)
def confirmar_disponibilidad(
    orden_id: int = Path(gt=0),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_solo_administrador),
    token: str = Depends(obtener_token_bearer),
    coordinador: CoordinadorDisponibilidadRepuestos = Depends(
        obtener_coordinador_disponibilidad_repuestos
    ),
) -> DisponibilidadRepuestosRespuesta:
    try:
        reserva = reservar_repuestos_aprobados(
            uow, orden_id=orden_id, actor_usuario_id=principal.usuario_id,
        )
    except RepuestosInsuficientesError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"mensaje": exc.mensaje, "faltantes": exc.faltantes},
        ) from exc
    except ConflictoDeDatos as exc:
        raise HTTPException(status_code=exc.codigo_http, detail=exc.mensaje) from exc

    uow.liberar_conexion()  # sin transacción abierta mientras responde MS2
    try:
        coordinador.aplicar(
            orden_id, str(reserva["clave_operacion"]), token
        )
    except ReservaRepuestosNoAplicableError as exc:
        # Un 4xx de MS2 se produce antes de confirmar su transacción, por lo que
        # el compromiso local puede liberarse con un movimiento compensatorio.
        revertir_reserva_rechazada(
            uow,
            orden_id=orden_id,
            clave_operacion=str(reserva["clave_operacion"]),
            actor_usuario_id=principal.usuario_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MS2 rechazó el cambio de estado; la reserva se liberó con un movimiento compensatorio",
        ) from exc
    except AplicacionDisponibilidadPendienteError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "mensaje": "La reserva quedó registrada, pero MS2 no confirmó el cambio de estado",
                "orden_id": exc.orden_id,
                "clave_operacion": exc.clave_operacion,
                "reintento": f"/api/inventario/ordenes/{orden_id}/disponibilidad",
            },
        ) from exc
    return DisponibilidadRepuestosRespuesta.model_validate(reserva)



@router.get(
    "/ordenes/{orden_id}/disponibilidad/{clave_operacion}",
    response_model=DisponibilidadRepuestosVerificada,
    summary="Verificar una reserva antes de iniciar reparación en MS2",
    include_in_schema=False,
)
def verificar_disponibilidad(
    orden_id: int = Path(gt=0),
    clave_operacion: str = Path(min_length=1, max_length=100),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    _: PrincipalAutenticado = Depends(_solo_administrador),
) -> dict[str, object]:
    try:
        return verificar_reserva_confirmada(
            uow, orden_id=orden_id, clave_operacion=clave_operacion,
        )
    except ConflictoDeDatos as exc:
        raise HTTPException(status_code=409, detail=exc.mensaje) from exc
