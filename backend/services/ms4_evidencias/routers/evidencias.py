"""Endpoints de evidencias (MS4).

    POST /evidencias                                   subir (Mecánico o Administrador)
    GET  /evidencias?orden_id=                         listar las de una orden
    GET  /evidencias/{evidencia_id}                    detalle de una evidencia
    GET  /evidencias/{evidencia_id}/descarga           URL prefirmada de descarga

Acceso (matriz de autorización, §4.5):
- Subir: solo Mecánico y Administrador (checklist 3.1); el 403 se resuelve en
  una dependencia, ANTES de leer el archivo de la petición.
- Consultar y descargar: cualquier rol autenticado. El Cliente aplica los tres
  filtros acumulativos (`visible_cliente = true`, `estado = confirmada`, no
  eliminada); el resto ve todas las no eliminadas; el Administrador ve todo,
  incluidas las eliminadas (auditoría).

Pendiente (tarea "Validar autorización y visibilidad"): verificar contra MS2
que la orden existe y pertenece al solicitante, y filtrar al mecánico por las
órdenes que atiende. Hasta entonces la decisión es solo por rol.

Errores: 401 sin token, 403 rol que no sube, 404 evidencia inexistente o fuera
de alcance, 422 datos/regla inválidos, 503 almacenamiento no disponible.
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


@router.post(
    "",
    response_model=EvidenciaLeida,
    status_code=status.HTTP_201_CREATED,
    summary="Subir una evidencia (foto o video) de una orden",
    description=(
        "Multipart: archivo + metadatos. El autor sale del JWT y el `request_id` de "
        "la cabecera X-Request-ID; el archivo se sube a MinIO/S3 y los metadatos a "
        "la base en una sola operación con compensación."
    ),
    responses={
        **_ERRORES_COMUNES,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Tipo de archivo, contexto o reglas de presupuesto inválidos"
        },
        **_503,
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
) -> EvidenciaLeida:
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
        "El cliente solo ve las visibles (`visible_cliente = true`, confirmadas y "
        "no eliminadas); el personal ve todas las no eliminadas."
    ),
    responses={
        **_401,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Falta `orden_id` o no es un entero positivo"
        },
    },
)
def listar(
    orden_id: int = Query(gt=0, description="Orden de trabajo (MS2) de las evidencias"),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[EvidenciaLeida]:
    return listar_por_orden(db, orden_id, vista_cliente=es_vista_cliente(principal))


@router.get(
    "/{evidencia_id}",
    response_model=EvidenciaLeida,
    summary="Detalle de una evidencia",
    description="Fuera del alcance se responde 404, no 403 (no revela existencia).",
    responses={**_401, **_NO_EXISTE},
)
def detalle(
    evidencia_id: UUID,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> EvidenciaLeida:
    evidencia = buscar_por_id(db, evidencia_id)
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
        "URL interna del almacenamiento. La respuesta incluye `Cache-Control: no-store`."
    ),
    responses={**_401, **_NO_EXISTE, **_503},
)
def descarga(
    evidencia_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    s3_publico: object = Depends(obtener_s3_publico),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> UrlDescarga:
    evidencia = buscar_por_id(db, evidencia_id)
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