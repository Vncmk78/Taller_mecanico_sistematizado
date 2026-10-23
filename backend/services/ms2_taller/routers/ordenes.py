"""Router de creación, listado y detalle inicial de órdenes de trabajo."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from services.ms2_taller.db import get_db
from services.ms2_taller.dependencies import obtener_principal_actual, obtener_token_bearer
from services.ms2_taller.integracion_ms3 import (
    DecisionNoAplicableError, DecisionNoVisibleError, ServicioPresupuestosNoDisponibleError,
    EnvioPresupuestoNoAplicableError, EnvioPresupuestoNoVisibleError,
    VerificadorDecisiones, VerificadorEnviosPresupuesto,
    obtener_verificador_decisiones, obtener_verificador_envios_presupuesto,
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
    OrdenEstadoInvalidoError,
    OrdenEstadoNoAutorizadoError,
    OrdenNoEncontradaError,
    OrdenObservacionInvalidaError,
    OrdenTerminalError,
    OrdenTransicionNoPermitidaError,
    PersistenciaOrdenError,
    VehiculoNoEncontradoError,
    asignar_mecanico,
    aplicar_decision_presupuesto,
    aplicar_envio_inicial_presupuesto,
    cambiar_estado_orden,
    confirmar_cancelacion_orden,
    crear_orden,
    listar_ordenes,
    obtener_historial_orden,
    obtener_orden_visible,
    listar_solicitudes_cancelacion_pendientes,
    solicitar_cancelacion_orden,
    registrar_entrega,
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
    AplicacionEnvioPresupuestoRespuesta,
    DecisionOrdenSolicitud,
    EnvioPresupuestoSolicitud,
)

router_ordenes = APIRouter(prefix="/ordenes", tags=["órdenes"])


@router_ordenes.get(
    "/configuracion/capacidad/ingresos-diarios",
    response_model=CupoDiarioIngresosRespuesta,
    summary="Consultar el cupo diario de ingresos físicos",
)
def consultar_cupo_diario_ingresos(
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> dict[str, object]:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operación",
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
    summary="Configurar el máximo diario de ingresos físicos",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "El máximo debe ser un entero positivo"
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
            detail="No tienes permiso para realizar esta operación",
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
    summary="Consultar el límite de órdenes activas por mecánico",
)
def consultar_capacidad_mecanicos(
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> dict[str, object]:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operación",
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
            detail="No fue posible consultar la capacidad de los mecánicos",
        ) from exc


@router_ordenes.put(
    "/configuracion/capacidad/mecanicos",
    response_model=CapacidadMecanicoRespuesta,
    summary="Configurar el máximo de órdenes activas por mecánico",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "El máximo debe ser un entero positivo"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible guardar la configuración"
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
            detail="No tienes permiso para realizar esta operación",
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
            detail="No fue posible guardar la capacidad de los mecánicos",
        ) from exc


@router_ordenes.post(
    "/{orden_id}/envios-presupuesto",
    response_model=AplicacionEnvioPresupuestoRespuesta,
    summary="Aplicar el envío inicial de presupuesto verificado en MS3",
    description=(
        "Solo Administrador. Recibe únicamente presupuesto_id, consulta el envío "
        "inicial a MS3 y deriva 2 → 3; no acepta actor ni estado destino. La "
        "referencia única en HistorialEstado hace idempotente el reintento. "
        "409 indica orden incompatible y 503 que no se pudo verificar el envío; "
        "los rechazos no cambian estado ni historial."
    ),
    responses={
        401: {"description": "JWT ausente o inválido"},
        403: {"description": "Se requiere rol Administrador"},
        404: {"description": "Orden o envío inicial inexistente"},
        409: {"description": "Estado incompatible con el envío inicial"},
        500: {"description": "Error de persistencia local"},
        503: {"description": "No fue posible verificar el envío en MS3"},
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
        raise HTTPException(404, "Orden o envío inicial no encontrado") from exc
    except OrdenEstadoNoAutorizadoError as exc:
        raise HTTPException(403, str(exc)) from exc
    except EnvioPresupuestoNoAplicableError as exc:
        raise HTTPException(409, str(exc)) from exc
    except OrdenTransicionNoPermitidaError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ServicioPresupuestosNoDisponibleError as exc:
        raise HTTPException(503, "No fue posible verificar el envío en MS3") from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(500, "No fue posible aplicar el envío del presupuesto") from exc


@router_ordenes.post(
    "/{orden_id}/decisiones-presupuesto", response_model=AplicacionDecisionRespuesta,
    summary="Aplicar una decisión inicial de presupuesto verificada en MS3",
    responses={
        401: {"description": "JWT ausente o inválido"},
        403: {"description": "Se requiere rol Cliente"},
        404: {"description": "Orden o decisión inexistente o ajena"},
        409: {"description": "Estado/evento incompatible o decisión no aplicable"},
        422: {"description": "Referencia inválida o cancelación sin motivo"},
        500: {"description": "Error de persistencia local"},
        503: {"description": "No fue posible verificar la decisión en MS3"},
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
        raise HTTPException(404, "Orden o decisión no encontrada") from exc
    except OrdenEstadoNoAutorizadoError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (OrdenTransicionNoPermitidaError, DecisionNoAplicableError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except OrdenObservacionInvalidaError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ServicioPresupuestosNoDisponibleError as exc:
        raise HTTPException(503, "No fue posible verificar la decisión en MS3") from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(500, "No fue posible aplicar la decisión") from exc


@router_ordenes.post(
    "",
    response_model=OrdenRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una orden de trabajo",
    description=(
        "Solo Administrador. Si el vehículo no tiene un ingreso físico abierto, "
        "se valida el cupo de la jornada local antes de registrar el nuevo ingreso. "
        "Una orden nueva que reutiliza un ingreso abierto no consume otro cupo."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_404_NOT_FOUND: {"description": "Vehículo no encontrado"},
        status.HTTP_409_CONFLICT: {
            "description": "Cupo diario agotado o aún no configurado"
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
    except CupoDiarioNoConfiguradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Configura el máximo diario de ingresos físicos antes de recibir vehículos",
        ) from exc
    except CupoDiarioExcedidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El taller ya alcanzó el máximo diario de ingresos físicos",
        ) from exc
    except VehiculoNoEncontradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehículo no encontrado",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible crear la orden",
        ) from exc


@router_ordenes.get(
    "",
    response_model=list[OrdenRespuesta],
    summary="Listar órdenes visibles",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la consulta"
        },
    },
)
def consultar_ordenes(
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[OrdenTrabajo]:
    try:
        return listar_ordenes(db, principal)
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar las órdenes",
        ) from exc


@router_ordenes.get(
    "/{orden_id}",
    response_model=OrdenRespuesta,
    summary="Consultar una orden visible",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
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
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la consulta"
        },
    },
)
def consultar_historial_orden(
    orden_id: int,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[HistorialEstado]:
    try:
        return obtener_historial_orden(db, principal, orden_id)
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
    summary="Consultar la bitácora de trabajo de una orden",
    description=(
        "Devuelve todos los registros por fecha/hora e identificador ascendente, "
        "con el autor, el tipo (observación o acción), el texto y los repuestos "
        "utilizados. Aplica la misma visibilidad del detalle: Administrador ve "
        "todas; Cliente sus vehículos; Mecánico sus órdenes asignadas; multirol "
        "combina los alcances. Una orden inexistente o ajena responde 404; una "
        "visible sin registros devuelve []."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la consulta"
        },
    },
)
def consultar_bitacora_orden(
    orden_id: int,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[BitacoraOrden]:
    try:
        return listar_bitacora_orden(db, principal, orden_id)
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar la bitácora de la orden",
        ) from exc


@router_ordenes.post(
    "/{orden_id}/bitacora",
    response_model=BitacoraRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una observación o acción en la bitácora",
    description=(
        "Registra lo que el mecánico observa o ejecuta sobre una orden sin "
        "cambiar su estado. Una observación es una nota libre; una acción puede "
        "declarar los repuestos utilizados (texto libre y cantidad). Solo el "
        "mecánico asignado o un administrador pueden registrarla. No acepta "
        "estado, actor ni fecha en el cuerpo."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {
            "description": "Se requiere ser el mecánico asignado o Administrador"
        },
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada o ajena"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Tipo, descripción o repuestos inválidos"
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar la entrada de la bitácora",
        ) from exc


@router_ordenes.patch(
    "/{orden_id}/estado",
    response_model=OrdenRespuesta,
    summary="Cambiar el estado de una orden",
    description=(
        "El PATCH genérico solo permite finalizar el trabajo (5 → 6) al Mecánico "
        "asignado. La asignación (1 → 2), el envío de presupuesto (2 → 3) y la "
        "decisión inicial (3 → 4/5/8) requieren sus operaciones específicas; "
        "3 → 8 está disponible solo por el rechazo inicial verificado, no por "
        "cancelación genérica. La "
        "disponibilidad de repuestos (4 → 5), entrega (6 → 7) y cancelación "
        "genérica están bloqueadas hasta contar con operaciones que verifiquen "
        "sus hechos de negocio."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {
            "description": "Se requiere rol Administrador o Mecánico asignado; solo este último finaliza el trabajo"
        },
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_409_CONFLICT: {
            "description": "Transición no permitida, terminal o reservada a una operación específica"
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Estado de destino desconocido, cancelación sin motivo o datos inválidos"
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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


@router_ordenes.put(
    "/{orden_id}/mecanico",
    response_model=OrdenRespuesta,
    summary="Asignar o reasignar el mecánico responsable",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_409_CONFLICT: {
            "description": (
                "Un administrador-mecánico no puede autoasignarse o la orden "
                "está en estado terminal, no se configuró capacidad o el "
                "mecánico alcanzó el límite"
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
) -> OrdenTrabajo:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise error_sin_permiso()
    if (
        NombreRol.MECANICO in principal.roles
        and body.mecanico_id == principal.usuario_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un mecánico no puede autoasignarse una orden",
        )

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
            detail="No fue posible asignar el mecánico",
        ) from exc


@router_ordenes.post(
    "/{orden_id}/entrega",
    response_model=OrdenRespuesta,
    summary="Registrar la entrega física de una orden lista",
    description=(
        "Cierra el ciclo normal (6 → 7): registra la fecha de entrega y el "
        "usuario que la autorizó. Solo el Administrador puede invocarla. "
        "Reemplaza al PATCH directo 6 → 7, que responde 409."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_409_CONFLICT: {
            "description": "La orden no está Lista o ya es terminal"
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Observación de entrega vacía"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
    },
)
def registrar_entrega_orden(
    orden_id: int,
    body: EntregaSolicitud,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> OrdenTrabajo:
    try:
        return registrar_entrega(
            db,
            orden_id=orden_id,
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
    except OrdenObservacionInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
            detail="No fue posible registrar la entrega",
        ) from exc


@router_ordenes.post(
    "/{orden_id}/cancelacion",
    response_model=SolicitudCancelacionRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar la cancelación administrativa de una orden",
    description=(
        "Solo el Cliente propietario. Registra motivo, actor y fecha sin cambiar "
        "el estado; el Administrador debe revisar y confirmar por la operación "
        "específica. MS3 se consulta para rechazar órdenes con aprobación inicial."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Cliente"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada o ajena"},
        status.HTTP_409_CONFLICT: {
            "description": "La orden avanzó, ya tiene solicitud o existe aprobación inicial"
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Motivo de cancelación vacío"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "No fue posible verificar la aprobación inicial en MS3"
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
            detail="No fue posible registrar la solicitud de cancelación",
        ) from exc
    except ServicioPresupuestosNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible verificar la aprobación inicial en MS3",
        ) from exc
    except DecisionNoVisibleError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Orden no encontrada") from exc


@router_ordenes.get(
    "/cancelaciones/pendientes",
    response_model=list[SolicitudCancelacionRespuesta],
    summary="Listar solicitudes de cancelación pendientes de revisión",
    responses={401: {"description": "JWT ausente o inválido"},
               403: {"description": "Se requiere rol Administrador"}},
)
def listar_cancelaciones_pendientes(
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[SolicitudCancelacionRespuesta]:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(status_code=403, detail="Se requiere rol Administrador")
    return [SolicitudCancelacionRespuesta.model_validate(solicitud)
            for solicitud in listar_solicitudes_cancelacion_pendientes(db)]


@router_ordenes.post(
    "/{orden_id}/cancelacion/confirmacion",
    response_model=OrdenRespuesta,
    summary="Confirmar administrativamente una solicitud de cancelación",
    description=(
        "Solo Administrador. Comprueba que la solicitud esté pendiente, que la "
        "orden siga en estado cancelable y vuelve a consultar a MS3 antes de "
        "registrar Cancelado e historial en una sola transacción."
    ),
    responses={401: {"description": "JWT ausente o inválido"},
               403: {"description": "Se requiere rol Administrador"},
               404: {"description": "Orden no encontrada"},
               409: {"description": "Solicitud no pendiente o aprobación inicial existente"},
               500: {"description": "No fue posible confirmar la cancelación"},
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
                            detail="No fue posible confirmar la cancelación") from exc
