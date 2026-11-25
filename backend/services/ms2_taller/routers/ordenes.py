"""Router de creaciÃ³n, listado y detalle inicial de Ã³rdenes de trabajo."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.orm import Session

from services.ms2_taller.db import get_db
from services.ms2_taller.dependencies import obtener_principal_actual, obtener_token_bearer
from services.ms2_taller.integracion_ms1 import (
    MecanicoNoValidoError,
    ServicioUsuariosNoDisponibleError,
    VerificadorMecanicos,
    obtener_verificador_mecanicos,
)
from services.ms2_taller.integracion_ms3 import (
    DecisionNoAplicableError, DecisionNoVisibleError, ServicioPresupuestosNoDisponibleError,
    EnvioPresupuestoNoAplicableError, EnvioPresupuestoNoVisibleError,
    DisponibilidadRepuestosNoAplicableError,
    DisponibilidadRepuestosNoVisibleError,
    VerificadorDecisiones, VerificadorEnviosPresupuesto,
    VerificadorDisponibilidadRepuestos,
    obtener_verificador_decisiones, obtener_verificador_envios_presupuesto,
    obtener_verificador_disponibilidad_repuestos,
    VerificadorAprobacionInicial, obtener_verificador_aprobacion_inicial,
)
from services.ms2_taller.models.historial_estado import HistorialEstado
from services.ms2_taller.models.bitacora_orden import BitacoraOrden
from services.ms2_taller.models.orden_trabajo import OrdenTrabajo
from services.ms2_taller.schemas.bitacora import BitacoraCrear, BitacoraRespuesta
from services.ms2_taller.schemas.orden import (
    AsignacionMecanicoActualizar,
    CapacidadMecanicoActualizar,
    CapacidadMecanicoRespuesta,
    CupoDiarioIngresosActualizar,
    CupoDiarioIngresosRespuesta,
    SolicitudCancelacionRespuesta,
    CambioEstadoSolicitud,
    EntregaOrdenRespuesta,
    DevolucionOrdenRespuesta,
    DevolucionSolicitud,
    DisponibilidadRepuestosRespuesta,
    HistorialOrdenesVehiculoRespuesta,
    CancelacionClienteSolicitud,
    EntregaSolicitud,
    HistorialEstadoRespuesta,
    OrdenCrear,
    OrdenRespuesta,
)
from services.ms2_taller.services.bitacora import (
    BitacoraEntradaInvalidaError,
    BitacoraNoAutorizadaError,
    BitacoraRepuestoInvalidoError,
    listar_bitacora_orden,
    registrar_entrada_bitacora,
)
from services.ms2_taller.services.ordenes import (
    EntregaOrdenInconsistenteError,
    SalidaVehiculoNoPermitidaError,
    OrdenEstadoInvalidoError,
    OrdenEstadoNoAutorizadoError,
    OrdenNoEncontradaError,
    OrdenObservacionInvalidaError,
    OrdenTerminalError,
    OrdenTransicionNoPermitidaError,
    PersistenciaOrdenError,
    VehiculoNoEncontradoError,
    VehiculoConOrdenActivaError,
    asignar_mecanico,
    aplicar_decision_presupuesto,
    aplicar_disponibilidad_repuestos,
    aplicar_envio_inicial_presupuesto,
    cambiar_estado_orden,
    confirmar_cancelacion_orden,
    crear_orden,
    listar_ordenes,
    listar_historial_ordenes_vehiculo,
    obtener_historial_orden,
    obtener_orden_visible,
    registrar_entrega_fisica,
    registrar_devolucion_fisica,
    listar_solicitudes_cancelacion_pendientes,
    solicitar_cancelacion_orden,
)
from services.ms2_taller.services.capacidad_mecanicos import (
    CapacidadMecanicoExcedidaError,
    CapacidadMecanicoNoConfiguradaError,
    PersistenciaCapacidadError,
    configurar_capacidad_mecanicos,
    obtener_configuracion_capacidad_mecanicos,
)
from services.ms2_taller.services.cupo_ingresos import (
    CupoDiarioExcedidoError,
    CupoDiarioNoConfiguradoError,
    PersistenciaCupoIngresosError,
    configurar_cupo_diario_ingresos,
    obtener_cupo_diario_ingresos,
)
from shared.auth import NombreRol, PrincipalAutenticado
from shared.errores_auth import error_sin_permiso
from shared.contratos_decisiones import (
    AplicacionDecisionRespuesta,
    AplicacionDisponibilidadRepuestosRespuesta,
    AplicacionEnvioPresupuestoRespuesta,
    DisponibilidadRepuestosSolicitud,
    DecisionOrdenSolicitud,
    EnvioPresupuestoSolicitud,
)

router_ordenes = APIRouter(prefix="/ordenes", tags=["Ã³rdenes"])
logger = logging.getLogger(__name__)
_REQUEST_ID_VALIDO = re.compile(r"[A-Za-z0-9-]{1,128}")
_SQLSTATE_VALIDO = re.compile(r"[A-Z0-9]{5}")


@router_ordenes.get(
    "/configuracion/capacidad/ingresos-diarios",
    response_model=CupoDiarioIngresosRespuesta,
    summary="Consultar el cupo diario de ingresos fÃ­sicos",
)
def consultar_cupo_diario_ingresos(
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> dict[str, object]:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operaciÃ³n",
        )
    try:
        configuracion, jornada, cantidad, excedido = obtener_cupo_diario_ingresos(db)
        return {
            "max_ingresos_diarios": configuracion.max_ingresos_diarios,
            "actualizado_por_id": configuracion.actualizado_por_id,
            "actualizado_en": configuracion.actualizado_en,
            "jornada_local": jornada,
            "ingresos_registrados": cantidad,
            "sobre_limite": excedido,
        }
    except PersistenciaCupoIngresosError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar el cupo diario de ingresos",
        ) from exc


@router_ordenes.put(
    "/configuracion/capacidad/ingresos-diarios",
    response_model=CupoDiarioIngresosRespuesta,
    summary="Configurar el mÃ¡ximo diario de ingresos fÃ­sicos",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "El mÃ¡ximo debe ser un entero positivo"
        },
    },
)
def actualizar_cupo_diario_ingresos(
    body: CupoDiarioIngresosActualizar,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> dict[str, object]:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operaciÃ³n",
        )
    try:
        configuracion, jornada, cantidad, excedido = configurar_cupo_diario_ingresos(
            db,
            max_ingresos_diarios=body.max_ingresos_diarios,
            administrador_id=principal.usuario_id,
        )
        return {
            "max_ingresos_diarios": configuracion.max_ingresos_diarios,
            "actualizado_por_id": configuracion.actualizado_por_id,
            "actualizado_en": configuracion.actualizado_en,
            "jornada_local": jornada,
            "ingresos_registrados": cantidad,
            "sobre_limite": excedido,
        }
    except PersistenciaCupoIngresosError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible guardar el cupo diario de ingresos",
        ) from exc


@router_ordenes.get(
    "/configuracion/capacidad/mecanicos",
    response_model=CapacidadMecanicoRespuesta,
    summary="Consultar el lÃ­mite de Ã³rdenes activas por mecÃ¡nico",
)
def consultar_capacidad_mecanicos(
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> dict[str, object]:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operaciÃ³n",
        )
    try:
        configuracion, sobre_limite = obtener_configuracion_capacidad_mecanicos(db)
        return {
            "max_ordenes_activas": configuracion.max_ordenes_activas,
            "actualizado_por_id": configuracion.actualizado_por_id,
            "actualizado_en": configuracion.actualizado_en,
            "mecanicos_sobre_limite": sobre_limite,
        }
    except PersistenciaCapacidadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar la capacidad de los mecÃ¡nicos",
        ) from exc


@router_ordenes.put(
    "/configuracion/capacidad/mecanicos",
    response_model=CapacidadMecanicoRespuesta,
    summary="Configurar el mÃ¡ximo de Ã³rdenes activas por mecÃ¡nico",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "El mÃ¡ximo debe ser un entero positivo"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible guardar la configuraciÃ³n"
        },
    },
)
def actualizar_capacidad_mecanicos(
    body: CapacidadMecanicoActualizar,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> dict[str, object]:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operaciÃ³n",
        )
    try:
        configuracion, sobre_limite = configurar_capacidad_mecanicos(
            db,
            max_ordenes_activas=body.max_ordenes_activas,
            administrador_id=principal.usuario_id,
        )
        return {
            "max_ordenes_activas": configuracion.max_ordenes_activas,
            "actualizado_por_id": configuracion.actualizado_por_id,
            "actualizado_en": configuracion.actualizado_en,
            "mecanicos_sobre_limite": sobre_limite,
        }
    except PersistenciaCapacidadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible guardar la capacidad de los mecÃ¡nicos",
        ) from exc


@router_ordenes.post(
    "/{orden_id}/envios-presupuesto",
    response_model=AplicacionEnvioPresupuestoRespuesta,
    summary="Aplicar el envÃ­o inicial de presupuesto verificado en MS3",
    description=(
        "Solo Administrador. Recibe Ãºnicamente presupuesto_id, consulta el envÃ­o "
        "inicial a MS3 y deriva 2 â†’ 3; no acepta actor ni estado destino. La "
        "referencia Ãºnica en HistorialEstado hace idempotente el reintento. "
        "409 indica orden incompatible y 503 que no se pudo verificar el envÃ­o; "
        "los rechazos no cambian estado ni historial."
    ),
    responses={
        401: {"description": "JWT ausente o invÃ¡lido"},
        403: {"description": "Se requiere rol Administrador"},
        404: {"description": "Orden o envÃ­o inicial inexistente"},
        409: {"description": "Estado incompatible con el envÃ­o inicial"},
        500: {"description": "Error de persistencia local"},
        503: {"description": "No fue posible verificar el envÃ­o en MS3"},
    },
)
def aplicar_envio_presupuesto(
    body: EnvioPresupuestoSolicitud,
    orden_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorEnviosPresupuesto = Depends(obtener_verificador_envios_presupuesto),
) -> AplicacionEnvioPresupuestoRespuesta:
    try:
        return aplicar_envio_inicial_presupuesto(
            db, orden_id=orden_id, presupuesto_id=body.presupuesto_id,
            principal=principal, token=token, verificador=verificador,
        )
    except (OrdenNoEncontradaError, EnvioPresupuestoNoVisibleError) as exc:
        raise HTTPException(404, "Orden o envÃ­o inicial no encontrado") from exc
    except OrdenEstadoNoAutorizadoError as exc:
        raise HTTPException(403, str(exc)) from exc
    except EnvioPresupuestoNoAplicableError as exc:
        raise HTTPException(409, str(exc)) from exc
    except OrdenTransicionNoPermitidaError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ServicioPresupuestosNoDisponibleError as exc:
        raise HTTPException(503, "No fue posible verificar el envÃ­o en MS3") from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(500, "No fue posible aplicar el envÃ­o del presupuesto") from exc


@router_ordenes.post(
    "/{orden_id}/decisiones-presupuesto", response_model=AplicacionDecisionRespuesta,
    summary="Aplicar una decisiÃ³n inicial de presupuesto verificada en MS3",
    responses={
        401: {"description": "JWT ausente o invÃ¡lido"},
        403: {"description": "Se requiere rol Cliente"},
        404: {"description": "Orden o decisiÃ³n inexistente o ajena"},
        409: {"description": "Estado/evento incompatible o decisiÃ³n no aplicable"},
        422: {"description": "Referencia invÃ¡lida o cancelaciÃ³n sin motivo"},
        500: {"description": "Error de persistencia local"},
        503: {"description": "No fue posible verificar la decisiÃ³n en MS3"},
    },
)
def aplicar_decision(
    body: DecisionOrdenSolicitud, orden_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorDecisiones = Depends(obtener_verificador_decisiones),
) -> AplicacionDecisionRespuesta:
    try:
        return aplicar_decision_presupuesto(
            db, orden_id=orden_id, decision_id=body.decision_id,
            principal=principal, token=token, verificador=verificador,
        )
    except (OrdenNoEncontradaError, DecisionNoVisibleError) as exc:
        raise HTTPException(404, "Orden o decisiÃ³n no encontrada") from exc
    except OrdenEstadoNoAutorizadoError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (OrdenTransicionNoPermitidaError, DecisionNoAplicableError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except OrdenObservacionInvalidaError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ServicioPresupuestosNoDisponibleError as exc:
        raise HTTPException(503, "No fue posible verificar la decisiÃ³n en MS3") from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(500, "No fue posible aplicar la decisiÃ³n") from exc


@router_ordenes.post(
    "/{orden_id}/disponibilidad-repuestos",
    response_model=AplicacionDisponibilidadRepuestosRespuesta,
    include_in_schema=False,
    summary="Iniciar reparaciÃ³n tras verificar una reserva de repuestos",
    description=(
        "Solo Administrador. MS2 valida la reserva persistida en MS3 antes de "
        "derivar Esperando repuestos â†’ En reparaciÃ³n. La clave de operaciÃ³n "
        "hace idempotente el reintento y queda registrada en el historial."
    ),
    responses={
        401: {"description": "JWT ausente o invÃ¡lido"},
        403: {"description": "Se requiere rol Administrador"},
        404: {"description": "Orden o reserva de repuestos no encontrada"},
        409: {"description": "Orden en estado incompatible o reserva no confirmada"},
        422: {"description": "Clave de operaciÃ³n invÃ¡lida"},
        500: {"description": "Error de persistencia local"},
        503: {"description": "No fue posible verificar la reserva en MS3"},
    },
)
def aplicar_disponibilidad(
    body: DisponibilidadRepuestosSolicitud,
    orden_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorDisponibilidadRepuestos = Depends(
        obtener_verificador_disponibilidad_repuestos
    ),
) -> AplicacionDisponibilidadRepuestosRespuesta:
    try:
        return aplicar_disponibilidad_repuestos(
            db,
            orden_id=orden_id,
            clave_operacion=body.clave_operacion,
            principal=principal,
            token=token,
            verificador=verificador,
        )
    except (OrdenNoEncontradaError, DisponibilidadRepuestosNoVisibleError) as exc:
        raise HTTPException(404, "Orden o reserva de repuestos no encontrada") from exc
    except OrdenEstadoNoAutorizadoError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (
        OrdenTransicionNoPermitidaError,
        DisponibilidadRepuestosNoAplicableError,
    ) as exc:
        raise HTTPException(409, str(exc)) from exc
    except ServicioPresupuestosNoDisponibleError as exc:
        raise HTTPException(503, "No fue posible verificar la reserva en MS3") from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(500, "No fue posible iniciar la reparaciÃ³n") from exc


@router_ordenes.post(
    "",
    response_model=OrdenRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una orden de trabajo",
    description=(
        "Solo Administrador. Si el vehÃ­culo no tiene un ingreso fÃ­sico abierto, "
        "se valida el cupo de la jornada local antes de registrar el nuevo ingreso. "
        "Una orden nueva que reutiliza un ingreso abierto no consume otro cupo. "
        "Solo se permite una orden activa por vehÃ­culo: cualquier estado salvo "
        "Entregado o Cancelado. Si existe otra, responde 409 sin crear registros."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_404_NOT_FOUND: {"description": "VehÃ­culo no encontrado"},
        status.HTTP_409_CONFLICT: {
            "description": "VehÃ­culo con orden activa, cupo diario agotado o aÃºn no configurado"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
    },
)
def registrar_orden(
    body: OrdenCrear,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> OrdenTrabajo:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise error_sin_permiso()

    try:
        return crear_orden(db, body.vehiculo_id, principal.usuario_id)
    except VehiculoConOrdenActivaError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CupoDiarioNoConfiguradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Configura el mÃ¡ximo diario de ingresos fÃ­sicos antes de recibir vehÃ­culos",
        ) from exc
    except CupoDiarioExcedidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El taller ya alcanzÃ³ el mÃ¡ximo diario de ingresos fÃ­sicos",
        ) from exc
    except VehiculoNoEncontradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VehÃ­culo no encontrado",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible crear la orden",
        ) from exc


@router_ordenes.get(
    "",
    response_model=list[OrdenRespuesta],
    summary="Listar Ã³rdenes visibles",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la consulta"
        },
    },
)
def consultar_ordenes(
    request: Request,
    response: Response,
    limite: int = Query(default=50, ge=1, le=100),
    desde: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[OrdenTrabajo]:
    try:
        ordenes, total = listar_ordenes(
            db, principal, limite=limite, desde=desde
        )
        response.headers["X-Total-Count"] = str(total)
        return ordenes
    except PersistenciaOrdenError as exc:
        request_id = request.headers.get("x-request-id", "")
        if not _REQUEST_ID_VALIDO.fullmatch(request_id):
            request_id = "no-disponible"
        causa = exc.__cause__
        sqlstate = getattr(getattr(causa, "orig", None), "sqlstate", None)
        if not isinstance(sqlstate, str) or not _SQLSTATE_VALIDO.fullmatch(sqlstate):
            sqlstate = "no-disponible"
        # No registrar la excepciÃ³n completa: puede contener SQL, parÃ¡metros o DSN.
        logger.error(
            "ms2_consulta_ordenes_fallida request_id=%s tipo=%s sqlstate=%s",
            request_id,
            type(causa).__name__ if causa is not None else "no-disponible",
            sqlstate,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar las Ã³rdenes",
        ) from exc


@router_ordenes.get(
    "/vehiculo/{vehiculo_id}/historial",
    response_model=HistorialOrdenesVehiculoRespuesta,
    summary="Consultar el historial paginado de Ã³rdenes de un vehÃ­culo",
    description=(
        "Ordena por fecha de creaciÃ³n descendente y desempata por ID. "
        "Cliente ve un vehÃ­culo propio, MecÃ¡nico solo Ã³rdenes actualmente "
        "asignadas a Ã©l y Administrador ve todas."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_404_NOT_FOUND: {"description": "VehÃ­culo no encontrado"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Identificador o parÃ¡metros de pÃ¡gina invÃ¡lidos"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible consultar el historial"
        },
    },
)
def consultar_historial_ordenes_vehiculo(
    vehiculo_id: int = Path(gt=0),
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int | None = Query(default=None, ge=0),
    limite: int | None = Query(default=None, ge=1, le=100),
    desde: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> dict[str, object]:
    # ``limite``/``desde`` son el contrato canÃ³nico; ``limit``/``offset`` se
    # conservan para los clientes que ya consumÃ­an este endpoint.
    limite = limite if limite is not None else (limit if limit is not None else 20)
    desde = desde if desde is not None else (offset if offset is not None else 0)
    try:
        items, total = listar_historial_ordenes_vehiculo(
            db, principal, vehiculo_id, limit=limite, offset=desde
        )
        return {"items": items, "total": total, "limit": limite, "offset": desde}
    except VehiculoNoEncontradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VehÃ­culo no encontrado",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar el historial del vehÃ­culo",
        ) from exc


@router_ordenes.get(
    "/{orden_id}",
    response_model=OrdenRespuesta,
    summary="Consultar una orden visible",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la consulta"
        },
    },
)
def consultar_orden(
    orden_id: int,
    response: Response,
    solo_propietario: bool = Query(
        default=False, description="Verificar propiedad del cliente, incluso con otros roles.",
    ),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> OrdenTrabajo:
    try:
        if solo_propietario:
            if NombreRol.CLIENTE not in principal.roles:
                raise OrdenNoEncontradaError("Orden no encontrada")
            # La visibilidad como personal no autoriza a decidir como cliente.
            principal = PrincipalAutenticado(
                principal.usuario_id, frozenset({NombreRol.CLIENTE}),
            )
        orden = obtener_orden_visible(db, principal, orden_id)
        if solo_propietario:
            response.headers["X-Orden-Propiedad-Verificada"] = "true"
        return orden
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar la orden",
        ) from exc


@router_ordenes.get(
    "/{orden_id}/historial",
    response_model=list[HistorialEstadoRespuesta],
    summary="Consultar el historial de estados de una orden",
    description=(
        "Devuelve todos los registros por fecha/hora e identificador ascendente. "
        "Aplica la misma visibilidad del detalle; sin registros devuelve []."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la consulta"
        },
    },
)
def consultar_historial_orden(
    orden_id: int,
    response: Response,
    limite: int = Query(default=50, ge=1, le=100),
    desde: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[HistorialEstado]:
    try:
        historial, total = obtener_historial_orden(
            db, principal, orden_id, limite=limite, desde=desde
        )
        response.headers["X-Total-Count"] = str(total)
        return historial
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar el historial de la orden",
        ) from exc


@router_ordenes.get(
    "/{orden_id}/bitacora",
    response_model=list[BitacoraRespuesta],
    summary="Consultar la bitÃ¡cora de trabajo de una orden",
    description=(
        "Devuelve todos los registros por fecha/hora e identificador ascendente, "
        "con el autor, el tipo (observaciÃ³n o acciÃ³n), el texto y los repuestos "
        "utilizados. Aplica la misma visibilidad del detalle: Administrador ve "
        "todas; Cliente sus vehÃ­culos; MecÃ¡nico sus Ã³rdenes asignadas; multirol "
        "combina los alcances. Una orden inexistente o ajena responde 404; una "
        "visible sin registros devuelve []."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la consulta"
        },
    },
)
def consultar_bitacora_orden(
    orden_id: int,
    response: Response,
    limite: int = Query(default=50, ge=1, le=100),
    desde: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[BitacoraOrden]:
    try:
        entradas, total = listar_bitacora_orden(
            db, principal, orden_id, limite=limite, desde=desde
        )
        response.headers["X-Total-Count"] = str(total)
        return entradas
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar la bitÃ¡cora de la orden",
        ) from exc


@router_ordenes.post(
    "/{orden_id}/bitacora",
    response_model=BitacoraRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una observaciÃ³n o acciÃ³n en la bitÃ¡cora",
    description=(
        "Registra lo que el mecÃ¡nico observa o ejecuta sobre una orden sin "
        "cambiar su estado. Una observaciÃ³n es una nota libre; una acciÃ³n puede "
        "declarar los repuestos utilizados (texto libre y cantidad). Solo el "
        "mecÃ¡nico asignado o un administrador pueden registrarla. No acepta "
        "estado, actor ni fecha en el cuerpo."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_403_FORBIDDEN: {
            "description": "Se requiere ser el mecÃ¡nico asignado o Administrador"
        },
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada o ajena"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Tipo, descripciÃ³n o repuestos invÃ¡lidos"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
    },
)
def registrar_bitacora_orden(
    orden_id: int,
    body: BitacoraCrear,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> BitacoraOrden:
    try:
        return registrar_entrada_bitacora(
            db,
            orden_id=orden_id,
            principal=principal,
            tipo=body.tipo,
            descripcion=body.descripcion,
            repuestos=[repuesto.model_dump() for repuesto in body.repuestos],
        )
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except BitacoraNoAutorizadaError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except (BitacoraEntradaInvalidaError, BitacoraRepuestoInvalidoError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar la entrada de la bitÃ¡cora",
        ) from exc


@router_ordenes.patch(
    "/{orden_id}/estado",
    response_model=OrdenRespuesta,
    summary="Cambiar el estado de una orden",
    description=(
        "El PATCH genÃ©rico solo permite finalizar el trabajo (5 â†’ 6) al MecÃ¡nico "
        "asignado. La asignaciÃ³n (1 â†’ 2), el envÃ­o de presupuesto (2 â†’ 3) y la "
        "decisiÃ³n inicial (3 â†’ 4/5/8) requieren sus operaciones especÃ­ficas; "
        "3 â†’ 8 estÃ¡ disponible solo por el rechazo inicial verificado, no por "
        "cancelaciÃ³n genÃ©rica. La "
        "disponibilidad de repuestos (4 â†’ 5), entrega (6 â†’ 7) y cancelaciÃ³n "
        "genÃ©rica estÃ¡n bloqueadas hasta contar con operaciones que verifiquen "
        "sus hechos de negocio."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_403_FORBIDDEN: {
            "description": "Se requiere rol Administrador o MecÃ¡nico asignado; solo este Ãºltimo finaliza el trabajo"
        },
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_409_CONFLICT: {
            "description": "TransiciÃ³n no permitida, terminal o reservada a una operaciÃ³n especÃ­fica"
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Estado de destino desconocido, cancelaciÃ³n sin motivo o datos invÃ¡lidos"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
    },
)
def cambiar_estado(
    orden_id: int,
    body: CambioEstadoSolicitud,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> OrdenTrabajo:
    try:
        return cambiar_estado_orden(
            db,
            orden_id=orden_id,
            estado_destino=body.estado_destino,
            principal=principal,
            observacion=body.observacion,
        )
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except OrdenEstadoNoAutorizadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except (OrdenEstadoInvalidoError, OrdenObservacionInvalidaError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except OrdenTransicionNoPermitidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible cambiar el estado de la orden",
        ) from exc


@router_ordenes.post(
    "/{orden_id}/entrega",
    response_model=EntregaOrdenRespuesta,
    summary="Registrar la entrega fÃ­sica de una orden",
    description=(
        "Solo un Administrador puede confirmar la entrega de una orden en "
        "estado Listo. El responsable y la fecha/hora se obtienen del JWT y "
        "del servidor. Repetir una entrega ya registrada devuelve el mismo "
        "registro, sin duplicar el historial. La primera entrega cierra el "
        "ingreso fÃ­sico en la misma transacciÃ³n; no corrige salidas histÃ³ricas."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_409_CONFLICT: {
            "description": "La orden debe estar en Listo para registrar su entrega"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible registrar la entrega fÃ­sica"
        },
    },
)
def confirmar_entrega_orden(
    orden_id: int,
    body: EntregaSolicitud | None = None,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> EntregaOrdenRespuesta:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol Administrador",
        )
    try:
        orden, historial = registrar_entrega_fisica(
            db,
            orden_id=orden_id,
            administrador_id=principal.usuario_id,
            observacion=body.observacion if body is not None else None,
        )
        return EntregaOrdenRespuesta(
            **OrdenRespuesta.model_validate(orden).model_dump(),
            entregado_en=orden.entregado_en,
            entregado_por_id=orden.entregado_por_id,
            historial_id=historial.historial_id,
        )
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except (OrdenTransicionNoPermitidaError, SalidaVehiculoNoPermitidaError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except EntregaOrdenInconsistenteError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La orden no conserva un registro de entrega completo",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar la entrega fÃ­sica",
        ) from exc


@router_ordenes.post(
    "/{orden_id}/devolucion",
    response_model=DevolucionOrdenRespuesta,
    summary="Registrar la devoluciÃ³n fÃ­sica de una orden cancelada",
    description=(
        "Solo Administrador. Conserva Cancelado, registra fecha del servidor y "
        "responsable del JWT, y cierra el ingreso en una sola transacciÃ³n. "
        "Un reintento conserva la auditorÃ­a original. No crea un cambio de "
        "estado ni permite salir mientras otra orden del ingreso siga activa."
    ),
    responses={
        401: {"description": "JWT ausente o invÃ¡lido"},
        403: {"description": "Se requiere rol Administrador"},
        404: {"description": "Orden no encontrada"},
        409: {"description": "Estado o ingreso incompatible con la devoluciÃ³n"},
        500: {"description": "No fue posible registrar la devoluciÃ³n fÃ­sica"},
    },
)
def confirmar_devolucion_orden(
    body: DevolucionSolicitud,
    orden_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> DevolucionOrdenRespuesta:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(status_code=403, detail="Se requiere rol Administrador")
    try:
        orden = registrar_devolucion_fisica(
            db, orden_id=orden_id, administrador_id=principal.usuario_id,
        )
        return DevolucionOrdenRespuesta.model_validate(orden)
    except OrdenNoEncontradaError as exc:
        raise HTTPException(status_code=404, detail="Orden no encontrada") from exc
    except SalidaVehiculoNoPermitidaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=500, detail="No fue posible registrar la devoluciÃ³n fÃ­sica",
        ) from exc


@router_ordenes.put(
    "/{orden_id}/mecanico",
    response_model=OrdenRespuesta,
    summary="Asignar o reasignar el mecÃ¡nico responsable",
    responses={
        422: {"description": "Destino inexistente, inactivo, sin rol MecÃ¡nico o datos invÃ¡lidos"},
        503: {"description": "MS1 no disponible para validar el destino; no se guarda el cambio"},
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_409_CONFLICT: {
            "description": (
                "Un administrador-mecÃ¡nico no puede autoasignarse o la orden "
                "estÃ¡ en estado terminal, no se configurÃ³ capacidad o el "
                "mecÃ¡nico alcanzÃ³ el lÃ­mite"
            )
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
    },
)
def actualizar_mecanico_responsable(
    orden_id: int,
    body: AsignacionMecanicoActualizar,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorMecanicos = Depends(obtener_verificador_mecanicos),
) -> OrdenTrabajo:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise error_sin_permiso()
    if (
        NombreRol.MECANICO in principal.roles
        and body.mecanico_id == principal.usuario_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un mecÃ¡nico no puede autoasignarse una orden",
        )

    try:
        verificador.verificar(body.mecanico_id, token)
    except MecanicoNoValidoError as exc:
        raise HTTPException(
            status_code=422,
            detail="El usuario de destino debe existir, estar activo y tener rol MecÃ¡nico",
        ) from exc
    except ServicioUsuariosNoDisponibleError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible validar el mecÃ¡nico con el servicio de usuarios",
        ) from exc

    try:
        return asignar_mecanico(
            db,
            orden_id=orden_id,
            mecanico_id=body.mecanico_id,
            administrador_id=principal.usuario_id,
            observacion=body.observacion,
        )
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except OrdenTerminalError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except CapacidadMecanicoNoConfiguradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except CapacidadMecanicoExcedidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible asignar el mecÃ¡nico",
        ) from exc




@router_ordenes.post(
    "/{orden_id}/cancelacion",
    response_model=SolicitudCancelacionRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar la cancelaciÃ³n administrativa de una orden",
    description=(
        "Solo el Cliente propietario. Registra motivo, actor y fecha sin cambiar "
        "el estado; el Administrador debe revisar y confirmar por la operaciÃ³n "
        "especÃ­fica. MS3 se consulta para rechazar Ã³rdenes con aprobaciÃ³n inicial."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o invÃ¡lido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Cliente"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada o ajena"},
        status.HTTP_409_CONFLICT: {
            "description": "La orden avanzÃ³, ya tiene solicitud o existe aprobaciÃ³n inicial"
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Motivo de cancelaciÃ³n vacÃ­o"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "No fue posible verificar la aprobaciÃ³n inicial en MS3"
        },
    },
)
def solicitar_cancelacion(
    orden_id: int,
    body: CancelacionClienteSolicitud,
    response: Response,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorAprobacionInicial = Depends(obtener_verificador_aprobacion_inicial),
) -> SolicitudCancelacionRespuesta:
    try:
        solicitud, creada = solicitar_cancelacion_orden(
            db,
            orden_id=orden_id,
            principal=principal,
            token=token,
            motivo=body.motivo,
            verificador=verificador,
        )
        response.status_code = status.HTTP_201_CREATED if creada else status.HTTP_200_OK
        return SolicitudCancelacionRespuesta.model_validate(solicitud)
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except OrdenEstadoNoAutorizadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except OrdenObservacionInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except OrdenTransicionNoPermitidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar la solicitud de cancelaciÃ³n",
        ) from exc
    except ServicioPresupuestosNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible verificar la aprobaciÃ³n inicial en MS3",
        ) from exc
    except DecisionNoVisibleError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Orden no encontrada") from exc


@router_ordenes.get(
    "/cancelaciones/pendientes",
    response_model=list[SolicitudCancelacionRespuesta],
    summary="Listar solicitudes de cancelaciÃ³n pendientes de revisiÃ³n",
    responses={401: {"description": "JWT ausente o invÃ¡lido"},
               403: {"description": "Se requiere rol Administrador"}},
)
def listar_cancelaciones_pendientes(
    response: Response,
    limite: int = Query(default=50, ge=1, le=100),
    desde: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[SolicitudCancelacionRespuesta]:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(status_code=403, detail="Se requiere rol Administrador")
    solicitudes, total = listar_solicitudes_cancelacion_pendientes(
        db, limite=limite, desde=desde
    )
    response.headers["X-Total-Count"] = str(total)
    return [SolicitudCancelacionRespuesta.model_validate(solicitud)
            for solicitud in solicitudes]


@router_ordenes.post(
    "/{orden_id}/cancelacion/confirmacion",
    response_model=OrdenRespuesta,
    summary="Confirmar administrativamente una solicitud de cancelaciÃ³n",
    description=(
        "Solo Administrador. Comprueba que la solicitud estÃ© pendiente, que la "
        "orden siga en estado cancelable y vuelve a consultar a MS3 antes de "
        "registrar Cancelado e historial en una sola transacciÃ³n."
    ),
    responses={401: {"description": "JWT ausente o invÃ¡lido"},
               403: {"description": "Se requiere rol Administrador"},
               404: {"description": "Orden no encontrada"},
               409: {"description": "Solicitud no pendiente o aprobaciÃ³n inicial existente"},
               500: {"description": "No fue posible confirmar la cancelaciÃ³n"},
               503: {"description": "No fue posible verificar MS3"}},
)
def confirmar_cancelacion(
    orden_id: int,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorAprobacionInicial = Depends(obtener_verificador_aprobacion_inicial),
) -> OrdenTrabajo:
    try:
        return confirmar_cancelacion_orden(
            db, orden_id=orden_id, principal=principal, token=token,
            verificador=verificador,
        )
    except OrdenNoEncontradaError as exc:
        raise HTTPException(status_code=404, detail="Orden no encontrada") from exc
    except OrdenEstadoNoAutorizadoError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OrdenTransicionNoPermitidaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DecisionNoVisibleError as exc:
        raise HTTPException(status_code=404, detail="Orden no encontrada") from exc
    except ServicioPresupuestosNoDisponibleError as exc:
        raise HTTPException(status_code=503, detail="No fue posible verificar MS3") from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(status_code=500,
                            detail="No fue posible confirmar la cancelaciÃ³n") from exc

