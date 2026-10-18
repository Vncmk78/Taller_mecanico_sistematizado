"""Lógica de dominio para recibir y consultar evidencias (flujo A).

Flujo A (fotos a través de MS4): el Gateway reenvía el archivo y sus metadatos;
MS4 lo sube a MinIO, guarda los metadatos en su PostgreSQL y compensa si algo
falla (no quedan archivos huérfanos ni filas sin archivo).

Las funciones NO reciben request, db.models, ni acumulan estado: reciben su
dependencia explícitamente (sesión, cliente S3, bucket) para poder ser testeadas
con SQLite y un FakeS3, y reutilizadas por los endpoints.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms4_evidencias.config import settings
from services.ms4_evidencias.models.evidencia import EstadoEvidencia, Evidencia
from services.ms4_evidencias.schemas.evidencia import DatosRecepcion
from services.ms4_evidencias.services.almacenamiento import (
    TamanoMaximoExcedido,
    calcular_sha256_y_tamano,
    eliminar_objeto,
    metadatos_objeto,
    subir_objeto,
)
from services.ms4_evidencias.services.contexto import normalizar_request_id
from services.ms4_evidencias.services.validacion_archivos import (
    MENSAJE_ARCHIVO_ILEGIBLE,
    ArchivoDanadoError,
    ArchivoDemasiadoGrandeError,
    ArchivoIlegibleError,
    ContenidoNoCoincideError,
    EvidenciaInvalidaError,
    PoliticaArchivos,
    TipoArchivoNoPermitidoError,
    normalizar_content_type,
    tipo_desde_content_type,
    validar_contenido,
)

__all__ = [
    "ArchivoDanadoError",
    "ArchivoDemasiadoGrandeError",
    "ArchivoIlegibleError",
    "ContenidoNoCoincideError",
    "EvidenciaInvalidaError",
    "PoliticaArchivos",
    "TipoArchivoNoPermitidoError",
    "normalizar_content_type",
    "tipo_desde_content_type",
]


class GuardadoEvidenciaError(Exception):
    """La base falló al guardar la evidencia después de subir el archivo (503).

    La subida ya se compensó (rollback + borrado del objeto). Si el borrado
    también falló, `clave_huerfana` trae la clave del objeto que quedó en el
    almacenamiento sin fila que lo respalde, para registrarlo y limpiarlo
    después; si la compensación funcionó, vale None. La causa original va
    encadenada (`__cause__`) y nunca se expone al cliente.
    """

    def __init__(
        self,
        clave_huerfana: str | None = None,
        evidencia_id: uuid.UUID | None = None,
    ) -> None:
        super().__init__("No se pudo guardar la evidencia")
        self.clave_huerfana = clave_huerfana
        self.evidencia_id = evidencia_id


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

# Convención única de clave (checklist 2.5): ordenes/{orden_id positivo}/{evidencia_id hex 32}.{ext}.
PATRON_CLAVE_OBJETO = re.compile(r"^ordenes/[1-9][0-9]*/[0-9a-f]{32}\.[a-z0-9]{2,5}$")


def generar_clave_objeto(
    orden_id: int,
    content_type: str,
    evidencia_id: uuid.UUID | None = None,
) -> str:
    """Clave del objeto en MinIO: ordenes/{orden_id}/{evidencia_id}.{ext}.

    El identificador de 32 caracteres es el `evidencia_id` (hex) cuando se
    pasa; si no (compatibilidad con llamadas anteriores, pruebas y flujo C),
    se genera un `uuid4` nuevo. La extensión sale del content_type, no del
    nombre original (checklist 1.4 y 2.5).
    """
    if orden_id <= 0:
        raise ValueError("orden_id debe ser un entero positivo")
    ct = normalizar_content_type(content_type)
    # Tipos fuera del mapa quedan como .bin: nunca se copia el subtipo recibido
    # a la clave (un content_type como "image/../../x" no puede alterar la ruta).
    # La lista blanca de formatos (control 1.1) se aplica antes, en
    # PoliticaArchivos.validar_tipo; este mapa solo decide la extensión.
    extension = _EXT_POR_CONTENT_TYPE.get(ct, "bin")
    identificador = (evidencia_id or uuid.uuid4()).hex
    return f"ordenes/{orden_id}/{identificador}.{extension}"


def es_clave_valida(clave: str) -> bool:
    """True si la clave cumple la convención PATRON_CLAVE_OBJETO.

    Sirve para validar claves que llegan de afuera (búsqueda, limpieza de
    huérfanos en Semana 6) sin confiar en prefijos ni segmentos arbitrarios.
    """
    return PATRON_CLAVE_OBJETO.fullmatch(clave) is not None


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
    *,
    politica: PoliticaArchivos | None = None,
) -> Evidencia:
    """Flujo A completo: valida, sube a MinIO y guarda los metadatos.

    Orden (para no dejar residuos):
    1. valida el content_type contra la lista blanca (1.1, → 415) y calcula el
       SHA-256 + tamaño en bloques de 1 MiB, cortando la lectura si supera el
       máximo de su tipo (1.3, → 413); un archivo de 0 bytes se rechaza (422);
       luego valida el contenido por su firma (1.2, → 415) y su estructura
       (1.6, → 422). El content_type que se guarda es el detectado, no el
       declarado. Todo esto ocurre ANTES de subir nada a MinIO;
    2. genera el evidencia_id y, a partir de él, la clave del objeto
       (filas y objetos comparten el mismo UUID: trazabilidad y, en Semana 6,
       limpieza de huérfanos por prefijo);
    3. sube el archivo a MinIO con los metadatos en x-amz-meta-* — si falla,
       se propaga y NO se crea ninguna fila;
    4. inserta la fila con estado `confirmada`, `confirmada_en` y `sha256` y hace
       commit;
    5. compensación: si la base falla, rollback y borra el objeto recién subido;
       se lanza `GuardadoEvidenciaError` (503) con la clave si el borrado
       también falló.

    Si el archivo recibido no se puede leer (OSError o archivo cerrado), se
    lanza `ArchivoIlegibleError` (400) antes de subir nada.
    """
    politica = politica or PoliticaArchivos.desde_settings(settings)
    content_type, tipo = politica.validar_tipo(content_type)

    try:
        sha256, tamano = calcular_sha256_y_tamano(
            archivo, maximo=politica.limite_para(tipo)
        )
    except TamanoMaximoExcedido as exc:
        raise politica.error_tamano(tipo) from exc
    except (OSError, ValueError) as exc:
        raise ArchivoIlegibleError(MENSAJE_ARCHIVO_ILEGIBLE) from exc
    if tamano == 0:
        raise EvidenciaInvalidaError("El archivo no puede estar vacío")
    try:
        content_type = validar_contenido(archivo, content_type, tamano, politica)
    except EvidenciaInvalidaError:
        raise
    except (OSError, ValueError) as exc:
        raise ArchivoIlegibleError(MENSAJE_ARCHIVO_ILEGIBLE) from exc

    evidencia_id = uuid.uuid4()
    clave = generar_clave_objeto(
        datos.orden_id, content_type, evidencia_id=evidencia_id
    )

    subir_objeto(
        s3,
        bucket,
        clave,
        archivo,
        content_type,
        metadatos=metadatos_objeto(
            evidencia_id,
            datos.orden_id,
            sha256,
            autor_usuario_id,
        ),
    )

    campos: dict = {
        "evidencia_id": evidencia_id,
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
        "request_id": normalizar_request_id(request_id),
        "confirmada_en": datetime.now(timezone.utc),
    }
    # visible_cliente: si no viene, rige el default por contexto del modelo.
    if datos.visible_cliente is not None:
        campos["visible_cliente"] = datos.visible_cliente

    evidencia = Evidencia(**campos)
    try:
        db.add(evidencia)
        db.commit()
    except Exception as exc:
        db.rollback()
        # Compensación: no dejar un archivo huérfano si la base falló.
        clave_huerfana: str | None = None
        try:
            eliminar_objeto(s3, bucket, clave)
        except Exception:  # noqa: BLE001  (la base ya falló; borrado best-effort)
            clave_huerfana = clave
        raise GuardadoEvidenciaError(clave_huerfana, evidencia_id) from exc
    db.refresh(evidencia)
    return evidencia


def listar_por_orden(
    db: Session, orden_id: int, *, vista_cliente: bool, incluir_eliminadas: bool = False
) -> list[Evidencia]:
    """Evidencias de una orden, filtradas según quien consulta.

    Cliente: solo `visible_cliente = true`, `estado = confirmada` y no eliminadas.
    Otros roles (mecánico): todas las no eliminadas.
    Admin (`incluir_eliminadas=True`): todas, incluidas las eliminadas
    (auditoría, matriz §4.5).
    Ordena por `creada_en`.
    """
    consulta = select(Evidencia).where(Evidencia.orden_id == orden_id)
    if not incluir_eliminadas:
        consulta = consulta.where(Evidencia.eliminada_en.is_(None))
    if vista_cliente:
        consulta = consulta.where(
            Evidencia.visible_cliente.is_(True),
            Evidencia.estado == EstadoEvidencia.CONFIRMADA,
        )
    consulta = consulta.order_by(Evidencia.creada_en)
    return list(db.scalars(consulta))


def buscar_por_id(db: Session, evidencia_id: uuid.UUID) -> Evidencia | None:
    """Evidencia por su UUID, o `None` si no existe."""
    return db.get(Evidencia, evidencia_id)


def es_visible_para(
    evidencia: Evidencia, *, vista_cliente: bool, es_admin: bool
) -> bool:
    """Regla de visibilidad de detalle/descarga, espejo de `listar_por_orden`.

    - Administrador: ve todo, incluidas las eliminadas (auditoría).
    - Eliminada lógicamente: solo la ve el administrador.
    - Vista cliente: los tres filtros acumulativos (`visible_cliente = true`,
      `estado = confirmada`, `eliminada_en IS NULL`).
    - Resto (personal): todas las no eliminadas, cualquier estado.
    """
    if es_admin:
        return True
    if evidencia.eliminada_en is not None:
        return False
    if vista_cliente:
        return (
            evidencia.visible_cliente
            and evidencia.estado == EstadoEvidencia.CONFIRMADA
        )
    return True


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
