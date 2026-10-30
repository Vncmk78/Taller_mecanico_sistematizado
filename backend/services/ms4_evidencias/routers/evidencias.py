"""Endpoints de evidencias (MS4).

    POST /evidencias                                   subir (Mecánico o Administrador)
    GET  /evidencias?orden_id=                         listar las de una orden
    GET  /evidencias/{evidencia_id}                    detalle de una evidencia
    GET  /evidencias/{evidencia_id}/descarga           URL prefirmada de descarga

Acceso (matriz de autorización, §4.5): MS4 vuelve a consultar a MS2
(`GET {MS2_URL}/ordenes/{orden_id}`, con el MISMO JWT, integracion_ms2.py) si
la orden existe y es visible para quien llama, en subir, listar, detalle y
descarga. MS2 responde 200 si la orden es de ese cliente o la atiende ese
mecánico; sobre esa respuesta MS4 mapea:

- Subir y listar: la orden debe ser visible para todos los roles; si MS2
  responde 404/403 → 404 "Orden no encontrada" (no enumera), y si MS2 no
  responde → 503.
- Detalle y descarga: si la evidencia no existe → 404 "Evidencia no
  encontrada". El Administrador NO consulta a MS2 (auditoría: ve todo,
  incluidas las eliminadas); el resto valida la orden contra MS2 y si MS2
  responde 404/403 también responde 404 "Evidencia no encontrada" — el mismo
  body que una evidencia inexistente, para no revelar existencia.

Roles sobre las evidencias:
- Subir: solo Mecánico y Administrador (checklist 3.1); el 403 se resuelve en
  una dependencia, ANTES de leer el archivo de la petición.
- Consultar: el Cliente aplica los tres filtros acumulativos
  (`visible_cliente = true`, `estado = confirmada`, no eliminada); el resto ve
  las no eliminadas; el Administrador ve todo, incluidas las eliminadas.

Archivo (Semana 6, checklist 1.1, 1.2, 1.3 y 1.6): solo se aceptan JPG, PNG,
WEBP, MP4 y MOV (415 para cualquier otro formato o si los bytes no
corresponden al formato declarado), cada tipo tiene un tamaño máximo
(`MS4_MAX_BYTES_FOTO` / `MS4_MAX_BYTES_VIDEO`, 413 si se supera) y un archivo
dañado o incompleto responde 422. Todos los rechazos ocurren antes de subir
nada a MinIO o crear filas.

Asociación con la orden (Semana 6): además de existir y ser visible (MS2), la
orden no puede estar entregada ni cancelada (409), y si la evidencia es de
contexto `presupuesto`, ese presupuesto debe pertenecer a la misma orden
(MS3, 422 si no existe o es de otra orden; 503 si MS3 no responde).

Errores: 400 archivo ilegible, 401 sin token, 403 rol que no sube, 404
evidencia/orden inexistente o fuera de alcance, 409 orden cerrada, 413 archivo
demasiado grande, 415 formato no permitido, 422 datos/regla/archivo dañado, 503
MS2, MS3, almacenamiento o base no disponible (la subida se compensa). Un error
no previsto responde 500 con un mensaje genérico (manejador en main.py).
"""
from __future__ import annotations

import logging
from uuid import UUID

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from services.ms4_evidencias.config import settings
from services.ms4_evidencias.db import get_db
from services.ms4_evidencias.dependencies import (
    obtener_principal_actual,
    obtener_s3,
    obtener_s3_publico,
    obtener_token_bearer,
)
from services.ms4_evidencias.integracion_ms2 import (
    ESTADOS_ORDEN_CERRADA,
    OrdenNoVisible,
    ServicioOrdenesNoDisponible,
    VerificadorOrdenes,
    obtener_verificador_ordenes,
)
from services.ms4_evidencias.integracion_ms3 import (
    PresupuestoNoEncontrado,
    ServicioPresupuestosNoDisponible,
    VerificadorPresupuestos,
    obtener_verificador_presupuestos,
)
from services.ms4_evidencias.models.evidencia import ContextoEvidencia, Evidencia
from services.ms4_evidencias.schemas.evidencia import (
    DatosRecepcion,
    EvidenciaLeida,
    UrlDescarga,
)
from services.ms4_evidencias.services.almacenamiento import generar_url_descarga
from services.ms4_evidencias.services.contexto import CABECERA_REQUEST_ID
from services.ms4_evidencias.services.evidencias import (
    GuardadoEvidenciaError,
    buscar_por_id,
    es_visible_para,
    listar_por_orden,
    recibir_evidencia,
)
from services.ms4_evidencias.services.permisos import (
    es_administrador,
    es_vista_cliente,
    puede_subir,
)
from services.ms4_evidencias.services.registro import nivel_para, registrar
from services.ms4_evidencias.services.validacion_archivos import (
    ArchivoDanadoError,
    ArchivoDemasiadoGrandeError,
    ArchivoIlegibleError,
    ContenidoNoCoincideError,
    EvidenciaInvalidaError,
    PoliticaArchivos,
    TipoArchivoNoPermitidoError,
)
from shared.auth import PrincipalAutenticado

router = APIRouter(prefix="/evidencias", tags=["evidencias"])

_MSG_ALMACENAMIENTO = "El almacenamiento de evidencias no está disponible"
_MSG_GUARDADO = "No se pudo guardar la evidencia, intenta nuevamente"
_MSG_ORDENES = "El servicio de órdenes no está disponible"
_MSG_PRESUPUESTOS = "El servicio de presupuestos no está disponible"
_MSG_ORDEN_CERRADA = "La orden está entregada o cancelada y no admite nuevas evidencias"
_MSG_PRESUPUESTO_NO_EXISTE = "El presupuesto indicado no existe"
_MSG_PRESUPUESTO_OTRA_ORDEN = "El presupuesto indicado no pertenece a la orden"

_401 = {status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente, inválido o expirado"}}
_403_SUBIR = {
    status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Mecánico o Administrador"}
}
_NO_EXISTE = {
    status.HTTP_404_NOT_FOUND: {"description": "Evidencia inexistente o fuera del alcance del solicitante"}
}
_503 = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "El almacenamiento de evidencias no está disponible"
    }
}
_503_ORDENES = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "El servicio de órdenes no está disponible (MS2)"
    }
}
_413 = {
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {
        "description": "El archivo supera el tamaño máximo de su tipo (foto o video)"
    }
}
_415 = {
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
        "description": "Formato no permitido: solo JPG, PNG, WEBP, MP4 y MOV"
    }
}
_ERRORES_COMUNES = {**_401, **_403_SUBIR}


def obtener_politica_archivos() -> PoliticaArchivos:
    """Lista blanca y límites de tamaño vigentes (configuración MS4_*)."""
    return PoliticaArchivos.desde_settings(settings)


def _personal_que_subira(
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> PrincipalAutenticado:
    """Guard 3.1: solo Mecánico o Administrador suben (antes de leer el archivo)."""
    if not puede_subir(principal):
        registrar(
            "subida_rechazada",
            logging.WARNING,
            motivo="rol_sin_permiso",
            estado_http=status.HTTP_403_FORBIDDEN,
            usuario_id=principal.usuario_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operación",
        )
    return principal


def _estado_y_motivo(exc: EvidenciaInvalidaError) -> tuple[int, str]:
    """Código HTTP y motivo corto (para el log) de un archivo rechazado."""
    if isinstance(exc, ArchivoDemasiadoGrandeError):
        return status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "demasiado_grande"
    if isinstance(exc, ContenidoNoCoincideError):
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "contenido_no_coincide"
    if isinstance(exc, TipoArchivoNoPermitidoError):
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "tipo_no_permitido"
    if isinstance(exc, ArchivoIlegibleError):
        return status.HTTP_400_BAD_REQUEST, "archivo_ilegible"
    if isinstance(exc, ArchivoDanadoError):
        return status.HTTP_422_UNPROCESSABLE_ENTITY, "archivo_danado"
    return status.HTTP_422_UNPROCESSABLE_ENTITY, "archivo_invalido"


def _accesible(evidencia: Evidencia | None, principal: PrincipalAutenticado) -> bool:
    """Detalle/descarga: 404 si no existe o está fuera del alcance (no enumeración)."""
    if evidencia is None:
        return False
    return es_visible_para(
        evidencia,
        vista_cliente=es_vista_cliente(principal),
        es_admin=es_administrador(principal),
    )


def _error_422_por_validacion(exc: ValidationError) -> HTTPException:
    """Reglas del schema (presupuesto/visible_cliente) como 422 de MS2/MS3."""
    detalle = " ".join(str(err["msg"]) for err in exc.errors())
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detalle)


def _exigir_orden_accesible(
    orden_id: int,
    token: str,
    verificador: VerificadorOrdenes,
    *,
    detalle_no_visible: str,
) -> int | None:
    """Valida la orden contra MS2 (mismo contrato que MS3, integracion_ms2.py).

    Devuelve el `estado_codigo` de la orden (None si MS2 no lo informa).
    404/403 de MS2 → 404 con `detalle_no_visible` (no enumera la existencia);
    MS2 no disponible → 503.
    """
    try:
        return verificador.verificar_acceso(orden_id, token)
    except OrdenNoVisible as exc:
        registrar(
            "acceso_rechazado",
            logging.WARNING,
            motivo="orden_no_visible",
            estado_http=status.HTTP_404_NOT_FOUND,
            orden_id=orden_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=detalle_no_visible
        ) from exc
    except ServicioOrdenesNoDisponible as exc:
        # Solo el tipo: el mensaje de httpx puede traer la URL interna de MS2.
        registrar(
            "dependencia_no_disponible",
            logging.ERROR,
            servicio="ms2",
            error=type(exc.__cause__ or exc).__name__,
            orden_id=orden_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_MSG_ORDENES
        ) from exc


def _exigir_orden_abierta(estado_codigo: int | None) -> None:
    """Una orden entregada o cancelada no admite nuevas evidencias (409)."""
    if estado_codigo in ESTADOS_ORDEN_CERRADA:
        registrar(
            "subida_rechazada",
            logging.WARNING,
            motivo="orden_cerrada",
            estado_http=status.HTTP_409_CONFLICT,
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_MSG_ORDEN_CERRADA)


def _exigir_presupuesto_de_la_orden(
    presupuesto_id: int,
    orden_id: int,
    token: str,
    verificador: VerificadorPresupuestos,
) -> None:
    """El presupuesto debe existir en MS3 y pertenecer a la misma orden.

    Inexistente o de otra orden → 422 (es un dato del formulario inválido);
    MS3 no disponible → 503. Se valida ANTES de leer o subir el archivo.
    """
    try:
        orden_del_presupuesto = verificador.orden_del_presupuesto(presupuesto_id, token)
    except PresupuestoNoEncontrado as exc:
        registrar(
            "subida_rechazada",
            logging.WARNING,
            motivo="presupuesto_inexistente",
            estado_http=status.HTTP_422_UNPROCESSABLE_ENTITY,
            presupuesto_id=presupuesto_id,
            orden_id=orden_id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_MSG_PRESUPUESTO_NO_EXISTE,
        ) from exc
    except ServicioPresupuestosNoDisponible as exc:
        registrar(
            "dependencia_no_disponible",
            logging.ERROR,
            servicio="ms3",
            error=type(exc.__cause__ or exc).__name__,
            presupuesto_id=presupuesto_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_MSG_PRESUPUESTOS
        ) from exc
    if orden_del_presupuesto != orden_id:
        registrar(
            "subida_rechazada",
            logging.WARNING,
            motivo="presupuesto_de_otra_orden",
            estado_http=status.HTTP_422_UNPROCESSABLE_ENTITY,
            presupuesto_id=presupuesto_id,
            orden_id=orden_id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_MSG_PRESUPUESTO_OTRA_ORDEN,
        )


@router.post(
    "",
    response_model=EvidenciaLeida,
    status_code=status.HTTP_201_CREATED,
    summary="Subir una evidencia (foto o video) de una orden",
    description=(
        "Multipart: archivo + metadatos. El autor sale del JWT y el `request_id` de "
        "la cabecera X-Request-ID; el archivo se sube a MinIO/S3 y los metadatos a "
        "la base en una sola operación con compensación. Antes de subir se valida "
        "contra MS2 que la orden existe, la atiende el solicitante y no está "
        "entregada ni cancelada (404/409/503), contra MS3 que el presupuesto es "
        "de esa orden, y el archivo: formato de la lista blanca verificado por "
        "su contenido (415), tamaño máximo (413) y estructura completa (422). "
        "Ningún rechazo deja archivos ni filas."
    ),
    responses={
        **_ERRORES_COMUNES,
        status.HTTP_400_BAD_REQUEST: {"description": "No se pudo leer el archivo enviado"},
        status.HTTP_404_NOT_FOUND: {
            "description": "La orden no existe o no la atiende el solicitante"
        },
        status.HTTP_409_CONFLICT: {
            "description": "La orden está entregada o cancelada"
        },
        **_413,
        **_415,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": (
                "Archivo vacío o dañado, contexto inválido, o presupuesto "
                "inexistente o de otra orden"
            )
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": (
                "El almacenamiento, la base, el servicio de órdenes (MS2) o el "
                "de presupuestos (MS3) no está disponible; no quedan archivos "
                "ni filas a medias"
            )
        },
    },
)
def subir(
    request: Request,
    archivo: UploadFile = File(...),
    orden_id: int = Form(gt=0),
    contexto: ContextoEvidencia = Form(...),
    presupuesto_id: int | None = Form(default=None, gt=0),
    visible_cliente: bool | None = Form(default=None),
    db: Session = Depends(get_db),
    s3: object = Depends(obtener_s3),
    principal: PrincipalAutenticado = Depends(_personal_que_subira),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorOrdenes = Depends(obtener_verificador_ordenes),
    politica: PoliticaArchivos = Depends(obtener_politica_archivos),
    verificador_presupuestos: VerificadorPresupuestos = Depends(
        obtener_verificador_presupuestos
    ),
) -> EvidenciaLeida:
    estado_orden = _exigir_orden_accesible(
        orden_id, token, verificador, detalle_no_visible="Orden no encontrada"
    )
    _exigir_orden_abierta(estado_orden)
    try:
        datos = DatosRecepcion(
            orden_id=orden_id,
            contexto=contexto,
            presupuesto_id=presupuesto_id,
            visible_cliente=visible_cliente,
        )
    except ValidationError as exc:
        registrar(
            "subida_rechazada",
            logging.WARNING,
            motivo="formulario_invalido",
            estado_http=status.HTTP_422_UNPROCESSABLE_ENTITY,
            orden_id=orden_id,
            usuario_id=principal.usuario_id,
        )
        raise _error_422_por_validacion(exc)
    if datos.presupuesto_id is not None:
        _exigir_presupuesto_de_la_orden(
            datos.presupuesto_id, datos.orden_id, token, verificador_presupuestos
        )

    try:
        evidencia = recibir_evidencia(
            db,
            s3,
            settings.S3_BUCKET,
            datos,
            archivo.file,
            archivo.filename or "",
            archivo.content_type or "",
            principal.usuario_id,
            request.headers.get(CABECERA_REQUEST_ID),
            politica=politica,
        )
    except EvidenciaInvalidaError as exc:
        estado_http, motivo = _estado_y_motivo(exc)
        registrar(
            "subida_rechazada",
            nivel_para(estado_http),
            motivo=motivo,
            estado_http=estado_http,
            orden_id=datos.orden_id,
            usuario_id=principal.usuario_id,
        )
        raise HTTPException(status_code=estado_http, detail=str(exc))
    except (BotoCoreError, ClientError, S3UploadFailedError) as exc:
        registrar(
            "subida_fallida",
            logging.ERROR,
            motivo="almacenamiento_no_disponible",
            servicio="s3",
            error=type(exc).__name__,
            orden_id=datos.orden_id,
            usuario_id=principal.usuario_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_MSG_ALMACENAMIENTO
        )
    except GuardadoEvidenciaError as exc:
        # La subida ya se compensó; el cliente puede reintentar. La causa real
        # (error de la base) queda encadenada y nunca viaja en el body. Si la
        # compensación no pudo borrar el objeto, el log lo marca para que la
        # conciliación (scripts/limpiar_huerfanos_ms4.py) lo limpie.
        registrar(
            "subida_fallida",
            logging.ERROR,
            motivo="base_no_disponible",
            error=type(exc.__cause__).__name__,
            evidencia_id=exc.evidencia_id,
            orden_id=datos.orden_id,
            usuario_id=principal.usuario_id,
            pendiente_limpieza=exc.clave_huerfana is not None,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_MSG_GUARDADO
        )
    registrar(
        "evidencia_subida",
        evidencia_id=evidencia.evidencia_id,
        orden_id=evidencia.orden_id,
        presupuesto_id=evidencia.presupuesto_id,
        contexto=evidencia.contexto,
        tipo_archivo=evidencia.tipo_archivo,
        content_type=evidencia.content_type,
        tamano_bytes=evidencia.tamano_bytes,
        usuario_id=principal.usuario_id,
    )
    return evidencia


@router.get(
    "",
    response_model=list[EvidenciaLeida],
    summary="Listar las evidencias de una orden",
    description=(
        "La orden se valida contra MS2 (404 si no existe o no pertenece al "
        "solicitante; 503 si MS2 no responde). El cliente solo ve las visibles "
        "(`visible_cliente = true`, confirmadas y no eliminadas); el personal ve "
        "las no eliminadas; el administrador ve todas, incluidas las eliminadas."
    ),
    responses={
        **_401,
        status.HTTP_404_NOT_FOUND: {
            "description": "La orden no existe o no pertenece al solicitante"
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Falta `orden_id` o no es un entero positivo"
        },
        **_503_ORDENES,
    },
)
def listar(
    orden_id: int = Query(gt=0, description="Orden de trabajo (MS2) de las evidencias"),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorOrdenes = Depends(obtener_verificador_ordenes),
) -> list[EvidenciaLeida]:
    _exigir_orden_accesible(
        orden_id, token, verificador, detalle_no_visible="Orden no encontrada"
    )
    return listar_por_orden(
        db,
        orden_id,
        vista_cliente=es_vista_cliente(principal),
        incluir_eliminadas=es_administrador(principal),
    )


@router.get(
    "/{evidencia_id}",
    response_model=EvidenciaLeida,
    summary="Detalle de una evidencia",
    description=(
        "Fuera del alcance se responde 404, no 403 (no revela existencia). La "
        "evidencia oculta responde el mismo 404 que una inexistente. El "
        "Administrador no consulta a MS2 (auditoría)."
    ),
    responses={**_401, **_NO_EXISTE, **_503_ORDENES},
)
def detalle(
    evidencia_id: UUID,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorOrdenes = Depends(obtener_verificador_ordenes),
) -> EvidenciaLeida:
    evidencia = buscar_por_id(db, evidencia_id)
    if evidencia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evidencia no encontrada"
        )
    if not es_administrador(principal):
        _exigir_orden_accesible(
            evidencia.orden_id,
            token,
            verificador,
            detalle_no_visible="Evidencia no encontrada",
        )
    if not _accesible(evidencia, principal):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evidencia no encontrada"
        )
    return evidencia


@router.get(
    "/{evidencia_id}/descarga",
    response_model=UrlDescarga,
    summary="URL prefirmada de corta duración para descargar la evidencia",
    description=(
        "Devuelve una URL firmada que expira (TTL de configuración) y fuerza el tipo "
        "y la descarga (controles 3.3 y 3.4). Nunca expone la clave del objeto ni la "
        "URL interna del almacenamiento. La respuesta incluye `Cache-Control: no-store`. "
        "Fuera del alcance responde 404 (mismo body que una evidencia inexistente); "
        "el Administrador no consulta a MS2."
    ),
    responses={**_401, **_NO_EXISTE, **_503, **_503_ORDENES},
)
def descarga(
    evidencia_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    s3_publico: object = Depends(obtener_s3_publico),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorOrdenes = Depends(obtener_verificador_ordenes),
) -> UrlDescarga:
    evidencia = buscar_por_id(db, evidencia_id)
    if evidencia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evidencia no encontrada"
        )
    if not es_administrador(principal):
        _exigir_orden_accesible(
            evidencia.orden_id,
            token,
            verificador,
            detalle_no_visible="Evidencia no encontrada",
        )
    if not _accesible(evidencia, principal):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evidencia no encontrada"
        )
    try:
        url = generar_url_descarga(
            s3_publico,
            settings.S3_BUCKET,
            evidencia.clave_objeto,
            content_type=evidencia.content_type,
            nombre_descarga=evidencia.nombre_original,
            expira_en=settings.URL_DESCARGA_TTL_SECONDS,
        )
    except (BotoCoreError, ClientError) as exc:
        registrar(
            "descarga_fallida",
            logging.ERROR,
            servicio="s3",
            error=type(exc).__name__,
            evidencia_id=evidencia.evidencia_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_MSG_ALMACENAMIENTO
        )
    # La URL firmada NUNCA se registra (checklist 5.5): da acceso al archivo.
    registrar(
        "descarga_autorizada",
        evidencia_id=evidencia.evidencia_id,
        orden_id=evidencia.orden_id,
        usuario_id=principal.usuario_id,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return UrlDescarga(url=url, expira_en=settings.URL_DESCARGA_TTL_SECONDS)