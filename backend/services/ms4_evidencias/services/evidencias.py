"""Lógica de dominio para recibir y consultar evidencias (flujo A).

Flujo A (fotos a través de MS4): el Gateway reenvía el archivo y sus metadatos;
MS4 lo sube a MinIO, guarda los metadatos en su PostgreSQL y compensa si algo
falla (no quedan archivos huérfanos ni filas sin archivo).

Las funciones NO reciben request, db.models, ni acumulan estado: reciben su
dependencia explícitamente (sesión, cliente S3, bucket) para poder ser testeadas
con SQLite y un FakeS3, y reutilizadas por los endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms4_evidencias.models.evidencia import (
    EstadoEvidencia,
    Evidencia,
    TipoArchivo,
)
from services.ms4_evidencias.schemas.evidencia import DatosRecepcion
from services.ms4_evidencias.services.almacenamiento import (
    calcular_sha256_y_tamano,
    eliminar_objeto,
    subir_objeto,
)


class EvidenciaInvalidaError(ValueError):
    """El archivo o su content_type no constituyen una evidencia válida."""


# Extensión de la clave según el content_type (1.4 y 2.5): la extensión sale del
# tipo de archivo, NUNCA del nombre que manda el usuario.
_EXT_POR_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/heic": "heic",
    "image/heif": "heif",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    "video/mpeg": "mpeg",
}


def normalizar_content_type(content_type: str) -> str:
    """content_type en minúsculas, sin parámetros (``; charset=...``) ni espacios.

    Se rechaza si no tiene la forma ``tipo/subtipo`` o si supera los 100
    caracteres de la columna: así nunca llega a la base un valor que haga fallar
    el INSERT después de haber subido el archivo.
    """
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    tipo, _, subtipo = ct.partition("/")
    if not tipo or not subtipo or len(ct) > 100:
        raise EvidenciaInvalidaError("Tipo de archivo no permitido")
    return ct


def tipo_desde_content_type(content_type: str) -> TipoArchivo:
    """Clasifica el content_type: image/* es foto, video/* es video."""
    ct = normalizar_content_type(content_type)
    if ct.startswith("image/"):
        return TipoArchivo.FOTO
    if ct.startswith("video/"):
        return TipoArchivo.VIDEO
    raise EvidenciaInvalidaError("Tipo de archivo no permitido")


def generar_clave_objeto(orden_id: int, content_type: str) -> str:
    """Clave del objeto en MinIO: ordenes/{orden_id}/{uuid}.{ext}.

    La extensión sale del content_type, no del nombre original del archivo
    (checklist 1.4 y 2.5).
    """
    ct = normalizar_content_type(content_type)
    # Tipos fuera del mapa quedan como .bin: nunca se copia el subtipo recibido
    # a la clave (un content_type como "image/../../x" no puede alterar la ruta).
    # La lista blanca real de formatos es el control 1.1 (Semana 6).
    extension = _EXT_POR_CONTENT_TYPE.get(ct, "bin")
    return f"ordenes/{orden_id}/{uuid.uuid4().hex}.{extension}"


def nombre_limpio(nombre: str) -> str:
    """Deja solo el nombre de archivo, sin rutas ni ``../`` (checklist 1.4).

    Es solo el nombre que se guarda como metadato para mostrar; la validación
    real del contenido (magic bytes) es del control 1.2 (Semana 6).
    """
    limpio = (nombre or "").replace("\\", "/").split("/")[-1].strip()
    if limpio in ("", ".", ".."):
        limpio = "archivo"
    return limpio[:255]


def recibir_evidencia(
    db: Session,
    s3: object,
    bucket: str,
    datos: DatosRecepcion,
    archivo,
    nombre_original: str,
    content_type: str,
    autor_usuario_id: int,
    request_id: str | None,
) -> Evidencia:
    """Flujo A completo: valida, sube a MinIO y guarda los metadatos.

    Orden (para no dejar residuos):
    1. valida el content_type y calcula el SHA-256 + tamaño (bloques de 1 MiB);
       un archivo de 0 bytes se rechaza ANTES de subir;
    2. genera la clave del objeto (UUID, extensión desde el content_type);
    3. sube el archivo a MinIO — si falla, se propaga y NO se crea ninguna fila;
    4. inserta la fila con estado `confirmada`, `confirmada_en` y `sha256` y hace
       commit;
    5. compensación: si la base falla, rollback y borra el objeto recién subido.
    """
    content_type = normalizar_content_type(content_type)
    tipo = tipo_desde_content_type(content_type)

    sha256, tamano = calcular_sha256_y_tamano(archivo)
    if tamano == 0:
        raise EvidenciaInvalidaError("El archivo no puede estar vacío")

    clave = generar_clave_objeto(datos.orden_id, content_type)

    subir_objeto(s3, bucket, clave, archivo, content_type)

    campos: dict = {
        "orden_id": datos.orden_id,
        "presupuesto_id": datos.presupuesto_id,
        "autor_usuario_id": autor_usuario_id,
        "contexto": datos.contexto,
        "tipo_archivo": tipo,
        "estado": EstadoEvidencia.CONFIRMADA,
        "clave_objeto": clave,
        "nombre_original": nombre_limpio(nombre_original),
        "content_type": content_type,
        "tamano_bytes": tamano,
        "sha256": sha256,
        "request_id": request_id[:64] if request_id else None,
        "confirmada_en": datetime.now(timezone.utc),
    }
    # visible_cliente: si no viene, rige el default por contexto del modelo.
    if datos.visible_cliente is not None:
        campos["visible_cliente"] = datos.visible_cliente

    evidencia = Evidencia(**campos)
    try:
        db.add(evidencia)
        db.commit()
    except Exception:
        db.rollback()
        # Compensación: no dejar un archivo huérfano si la base falló.
        try:
            eliminar_objeto(s3, bucket, clave)
        except Exception:  # noqa: BLE001  (la base ya falló; borrado best-effort)
            pass
        raise
    db.refresh(evidencia)
    return evidencia


def listar_por_orden(db: Session, orden_id: int, *, vista_cliente: bool) -> list[Evidencia]:
    """Evidencias de una orden, filtradas según quien consulta.

    Cliente: solo `visible_cliente = true`, `estado = confirmada` y no eliminadas.
    Otros roles (mecánico/admin): todas las no eliminadas.
    Ordena por `creada_en`.
    """
    consulta = select(Evidencia).where(
        Evidencia.orden_id == orden_id,
        Evidencia.eliminada_en.is_(None),
    )
    if vista_cliente:
        consulta = consulta.where(
            Evidencia.visible_cliente.is_(True),
            Evidencia.estado == EstadoEvidencia.CONFIRMADA,
        )
    consulta = consulta.order_by(Evidencia.creada_en)
    return list(db.scalars(consulta))


def presupuesto_tiene_evidencia(db: Session, presupuesto_id: int) -> bool:
    """RF18: el presupuesto tiene al menos una evidencia confirmada y vigente.

    Las eliminadas lógicamente NO cuentan (regla del modelo).
    """
    existe = (
        select(Evidencia.evidencia_id)
        .where(
            Evidencia.presupuesto_id == presupuesto_id,
            Evidencia.estado == EstadoEvidencia.CONFIRMADA,
            Evidencia.eliminada_en.is_(None),
        )
        .limit(1)
    )
    return db.scalar(existe) is not None
