"""Detección y limpieza de archivos huérfanos en el almacenamiento (Semana 6).

Un objeto huérfano es un archivo en MinIO/S3 sin una fila en la tabla de
evidencias que lo respalde. La recepción ya evita la mayoría (sube primero,
inserta después y, si la base falla, borra el objeto: compensación en
`recibir_evidencia`), pero quedan dos casos que la compensación no cubre:

- la base falla y el borrado de compensación TAMBIÉN falla
  (`GuardadoEvidenciaError.clave_huerfana`);
- el proceso muere entre la subida y el commit (no alcanza a compensar).

Este módulo hace la conciliación entre el bucket y la base:

1. Lista los objetos bajo `ordenes/` (paginado, 1000 por página).
2. Ignora y reporta como "ajenas" las claves que no cumplen la convención
   `PATRON_CLAVE_OBJETO` (checklist 2.5): nunca se borra algo que MS4 no creó.
3. Solo considera candidatos los objetos más antiguos que `antiguedad_minima`
   (por defecto 60 minutos): una subida en curso tiene el objeto pero aún no
   la fila, y no debe confundirse con un huérfano.
4. Compara contra la columna `clave_objeto` (no contra el UUID del nombre),
   así también respeta claves antiguas generadas antes de que la clave usara
   el `evidencia_id`. Las evidencias eliminadas lógicamente conservan su fila
   y por lo tanto su archivo NO es huérfano.
5. Por defecto solo reporta (simulación). Borra únicamente con
   `eliminar=True`, objeto por objeto, y anota los que no pudo borrar.

Además informa el caso inverso: filas confirmadas y vigentes cuyo archivo ya
no existe en el bucket. Esas no se tocan (requieren revisión manual).
"""
from __future__ import annotations

import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms4_evidencias.models.evidencia import EstadoEvidencia, Evidencia
from services.ms4_evidencias.services.evidencias import es_clave_valida

PREFIJO_EVIDENCIAS = "ordenes/"
ANTIGUEDAD_MINIMA_POR_DEFECTO = timedelta(minutes=60)
# Tamaño de los lotes del `IN (...)` contra la base.
_TAMANO_LOTE = 500


@dataclass
class ResultadoConciliacion:
    """Lo que encontró (y, si se pidió, limpió) una pasada de conciliación."""

    revisados: int = 0
    huerfanos: list[str] = field(default_factory=list)
    eliminados: list[str] = field(default_factory=list)
    no_eliminados: list[str] = field(default_factory=list)
    recientes: int = 0
    claves_ajenas: list[str] = field(default_factory=list)
    filas_sin_objeto: list[uuid.UUID] = field(default_factory=list)
    # False = simulación: solo se reporta, no se borra nada.
    eliminar: bool = False


def _listar_objetos(s3: object, bucket: str, prefijo: str) -> Iterator[dict]:
    """Recorre todos los objetos del prefijo siguiendo la paginación de S3."""
    argumentos: dict = {"Bucket": bucket, "Prefix": prefijo}
    while True:
        pagina = s3.list_objects_v2(**argumentos)
        yield from pagina.get("Contents", [])
        if not pagina.get("IsTruncated"):
            return
        argumentos["ContinuationToken"] = pagina["NextContinuationToken"]


def _lotes(valores: list[str], tamano: int = _TAMANO_LOTE) -> Iterable[list[str]]:
    for inicio in range(0, len(valores), tamano):
        yield valores[inicio : inicio + tamano]


def _claves_con_fila(db: Session, claves: list[str]) -> set[str]:
    """Subconjunto de `claves` que tiene fila en la tabla (incluye eliminadas)."""
    encontradas: set[str] = set()
    for lote in _lotes(claves):
        encontradas.update(
            db.scalars(select(Evidencia.clave_objeto).where(Evidencia.clave_objeto.in_(lote)))
        )
    return encontradas


def _como_utc(momento: datetime) -> datetime:
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def conciliar(
    db: Session,
    s3: object,
    bucket: str,
    *,
    antiguedad_minima: timedelta = ANTIGUEDAD_MINIMA_POR_DEFECTO,
    eliminar: bool = False,
    ahora: datetime | None = None,
) -> ResultadoConciliacion:
    """Compara bucket y base; con `eliminar=True` borra los objetos huérfanos.

    Nunca borra claves fuera de la convención ni objetos más recientes que
    `antiguedad_minima`. Un fallo al borrar un objeto no detiene la pasada:
    queda en `no_eliminados` para reintentar en la siguiente.
    """
    ahora = ahora or datetime.now(timezone.utc)
    limite = ahora - antiguedad_minima
    resultado = ResultadoConciliacion(eliminar=eliminar)
    candidatas: list[str] = []
    claves_en_bucket: set[str] = set()

    for objeto in _listar_objetos(s3, bucket, PREFIJO_EVIDENCIAS):
        resultado.revisados += 1
        clave = objeto["Key"]
        if not es_clave_valida(clave):
            resultado.claves_ajenas.append(clave)
            continue
        claves_en_bucket.add(clave)
        if _como_utc(objeto["LastModified"]) > limite:
            resultado.recientes += 1
            continue
        candidatas.append(clave)

    con_fila = _claves_con_fila(db, candidatas)
    resultado.huerfanos = sorted(set(candidatas) - con_fila)

    if eliminar:
        for clave in resultado.huerfanos:
            try:
                s3.delete_object(Bucket=bucket, Key=clave)
            except Exception:  # noqa: BLE001  (se reintenta en la próxima pasada)
                resultado.no_eliminados.append(clave)
            else:
                resultado.eliminados.append(clave)

    resultado.filas_sin_objeto = _filas_sin_objeto(db, claves_en_bucket, limite)
    return resultado


def _filas_sin_objeto(
    db: Session, claves_en_bucket: set[str], limite: datetime
) -> list[uuid.UUID]:
    """Evidencias confirmadas, vigentes y no recientes cuyo archivo no está.

    Solo se reportan: borrar o anular la fila es una decisión de negocio
    (podría ser evidencia de un presupuesto aprobado, checklist 5.2).
    """
    filas = db.execute(
        select(Evidencia.evidencia_id, Evidencia.clave_objeto, Evidencia.creada_en).where(
            Evidencia.estado == EstadoEvidencia.CONFIRMADA,
            Evidencia.eliminada_en.is_(None),
        )
    )
    return sorted(
        evidencia_id
        for evidencia_id, clave, creada_en in filas
        if clave not in claves_en_bucket
        and (creada_en is None or _como_utc(creada_en) <= limite)
    )
