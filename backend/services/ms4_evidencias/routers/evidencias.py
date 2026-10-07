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

Errores: 401 sin token, 403 rol que no sube, 404 evidencia/orden inexistente o
fuera de alcance, 422 datos/regla inválidos, 503 MS2 u almacenamiento no
disponible.
"""
from __future__ import annotations

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
    OrdenNoVisible,
    ServicioOrdenesNoDisponible,
    VerificadorOrdenes,
    obtener_verificador_ordenes,
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
    EvidenciaInvalidaError,
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
from shared.auth import PrincipalAutenticado

router = APIRouter(prefix="/evidencias", tags=["evidencias"])

_MSG_ALMACENAMIENTO = "El almacenamiento de evidencias no está disponible"
_MSG_ORDENES = "El servicio de órdenes no está disponible"

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
_ERRORES_COMUNES = {**_401, **_403_SUBIR}


def _personal_que_subira(
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> PrincipalAutenticado:
    """Guard 3.1: solo Mecánico o Administrador suben (antes de leer el archivo)."""
    if not puede_subir(principal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operación",
        )
    return principal


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
) -> None:
    """Valida la orden contra MS2 (mismo contrato que MS3, integracion_ms2.py).

    404/403 de MS2 → 404 con `detalle_no_visible` (no enumera la existencia);
    MS2 no disponible → 503.
    """
    try:
        verificador.verificar_acceso(orden_id, token)
    except OrdenNoVisible as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=detalle_no_visible
        ) from exc
    except ServicioOrdenesNoDisponible as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_MSG_ORDENES
        ) from exc


@router.post(
    "",
    response_model=EvidenciaLeida,
    status_code=status.HTTP_201_CREATED,
    summary="Subir una evidencia (foto o video) de una orden",
    description=(
        "Multipart: archivo + metadatos. El autor sale del JWT y el `request_id` de "
        "la cabecera X-Request-ID; el archivo se sube a MinIO/S3 y los metadatos a "
        "la base en una sola operación con compensación. Antes de subir se valida "
        "contra MS2 que la orden existe y la atiende el solicitante (404/503 sin "
        "dejar archivos ni filas)."
    ),
    responses={
        **_ERRORES_COMUNES,
        status.HTTP_404_NOT_FOUND: {
            "description": "La orden no existe o no la atiende el solicitante"
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Tipo de archivo, contexto o reglas de presupuesto inválidos"
        },
        **_503,
        **_503_ORDENES,
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
) -> EvidenciaLeida:
    _exigir_orden_accesible(
        orden_id, token, verificador, detalle_no_visible="Orden no encontrada"
    )
    try:
        datos = DatosRecepcion(
            orden_id=orden_id,
            contexto=contexto,
            presupuesto_id=presupuesto_id,
            visible_cliente=visible_cliente,
        )
    except ValidationError as exc:
        raise _error_422_por_validacion(exc)

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
        )
    except EvidenciaInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except (BotoCoreError, ClientError, S3UploadFailedError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_MSG_ALMACENAMIENTO
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
    except (BotoCoreError, ClientError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_MSG_ALMACENAMIENTO
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return UrlDescarga(url=url, expira_en=settings.URL_DESCARGA_TTL_SECONDS)