"""Modelo Evidencia (MS4: Evidencia Multimedia).

MER (recuadro "BD MS4"):
  evidencia_id, orden_id REF → MS2, autor_usuario_id REF → MS1, contexto,
  visible_cliente, tipo_archivo, clave_objeto, creada_en, eliminada_en?

Agregados por el estudio de almacenamiento y la auditoría:
  presupuesto_id? REF → MS3, estado, nombre_original, content_type,
  tamano_bytes, sha256?, request_id?, confirmada_en?,
  eliminada_por_usuario_id? REF → MS1

Estudio de almacenamiento (tarea "Estudiar MinIO/S3, multipart y SDK"):
  - La evidencia tiene DOS piezas: el archivo vive en MinIO/S3 (clave_objeto,
    tamaño, sha256) y el METADATO vive acá, en el PostgreSQL de MS4. En este
    microservicio nunca guardamos el archivo en la base.
  - `clave_objeto` es la única referencia al objeto; el nombre original solo
    sirve para mostrarlo y NUNCA para construir rutas (checklist 2.5).
  - `sha256` se llena cuando la evidencia pasa a CONFIRMADA (flujo C): hasta
    entonces no hay hash que validar. El cálculo/comparación ya quedó probado
    en la "Prueba mínima" (scripts/prueba_minio.py).

Referencias lógicas (Sistematización final §8: aislamiento de datos): las PK
de órdenes (MS2), presupuestos (MS3) y usuarios (MS1) son enteros seriales, así
que `orden_id`, `presupuesto_id`, `autor_usuario_id` y `eliminada_por_usuario_id`
son Integer SIN ForeignKey: nunca cruzamos claves foráneas físicas entre bases.

Los enums se declaran como StrEnum y se guardan como strings, validados con
CHECK (reglas 1 a 3). `visible_cliente` nace con un valor por defecto que
depende del contexto (reglas de visibilidad): en presupuesto siempre true y no
se puede cambiar (regla 7).

Eliminación LÓGICA (MER §4.4): cancelar una orden no borra sus evidencias;
`eliminada_en` / `eliminada_por_usuario_id` solo marcan la baja para auditoría.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from services.ms4_evidencias.db import Base


class ContextoEvidencia(StrEnum):
    """En qué etapa de la orden se adjuntó la evidencia (MER: contexto)."""

    DIAGNOSTICO = "diagnostico"
    PRESUPUESTO = "presupuesto"
    REPARACION = "reparacion"
    RESULTADO_FINAL = "resultado_final"


class TipoArchivo(StrEnum):
    """Clasificación de la evidencia (MER: tipo_archivo)."""

    FOTO = "foto"
    VIDEO = "video"


class EstadoEvidencia(StrEnum):
    """Ciclo de vida de la evidencia (flujo C, estudio de almacenamiento).

    pendiente → confirmada → eliminación lógica
    pendiente → anulada
    """

    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    ANULADA = "anulada"


def _visible_por_contexto(context) -> bool:
    """Valor por defecto de `visible_cliente` según el contexto de la fila.

    diagnostico y reparacion: false (trabajo interno del taller).
    presupuesto: true (el cliente aprueba viendo la evidencia) y la regla 7
        impide guardarla en false.
    resultado_final: true (entrega de la orden).
    """
    parametros = context.get_current_parameters()
    contexto = parametros.get("contexto")
    return contexto in (
        ContextoEvidencia.PRESUPUESTO.value,
        ContextoEvidencia.RESULTADO_FINAL.value,
    )


class Evidencia(Base):
    __tablename__ = "evidencia"

    __table_args__ = (
        # Consulta principal de la recepción: evidencias de una orden por contexto.
        Index("ix_evidencia_orden_contexto", "orden_id", "contexto"),
        # Soporta RF18 y la regla "todo presupuesto incluye al menos una evidencia".
        Index("ix_evidencia_presupuesto", "presupuesto_id"),
        # Regla 1: contexto dentro de los 4 valores del MER.
        CheckConstraint(
            "contexto in ('diagnostico', 'presupuesto', 'reparacion', 'resultado_final')",
            name="contexto_valido",
        ),
        # Regla 2: tipo_archivo es foto o video.
        CheckConstraint("tipo_archivo in ('foto', 'video')", name="tipo_archivo_valido"),
        # Regla 3: estado dentro de los 3 valores del flujo C.
        CheckConstraint(
            "estado in ('pendiente', 'confirmada', 'anulada')", name="estado_valido"
        ),
        # Regla 4: un archivo de evidencia siempre pesa más que cero.
        CheckConstraint("tamano_bytes > 0", name="tamano_positivo"),
        # Regla 5: si hay sha256, es un hash hex de 64 caracteres (SHA-256).
        CheckConstraint("sha256 is null or length(sha256) = 64", name="sha256_longitud_64"),
        # Regla 6: contexto presupuesto ⟷ presupuesto_id, ambos juntos o ambos no.
        CheckConstraint(
            "(contexto = 'presupuesto' and presupuesto_id is not null) "
            "or (contexto <> 'presupuesto' and presupuesto_id is null)",
            name="presupuesto_coherente",
        ),
        # Regla 7: la evidencia del presupuesto SIEMPRE es visible para el cliente.
        CheckConstraint(
            "contexto <> 'presupuesto' or visible_cliente = true",
            name="presupuesto_siempre_visible",
        ),
        # Regla 8: confirmada exige fecha de confirmación y sha256 (control 2.4).
        CheckConstraint(
            "estado <> 'confirmada' or (confirmada_en is not null and sha256 is not null)",
            name="confirmada_completa",
        ),
        # Regla 9: eliminación lógica — o están los dos campos o ninguno.
        CheckConstraint(
            "(eliminada_en is null) = (eliminada_por_usuario_id is null)",
            name="eliminacion_completa",
        ),
        # Referencias lógicas a MS1/MS2/MS3: ids positivos (mismo criterio que MS2).
        CheckConstraint(
            "orden_id > 0 and autor_usuario_id > 0 "
            "and (presupuesto_id is null or presupuesto_id > 0) "
            "and (eliminada_por_usuario_id is null or eliminada_por_usuario_id > 0)",
            name="referencias_positivas",
        ),
    )

    evidencia_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    orden_id: Mapped[int] = mapped_column(Integer, nullable=False)
    presupuesto_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    autor_usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)

    contexto: Mapped[str] = mapped_column(String(20), nullable=False)
    tipo_archivo: Mapped[str] = mapped_column(String(10), nullable=False)
    visible_cliente: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=_visible_por_contexto
    )
    estado: Mapped[str] = mapped_column(
        String(12), nullable=False, default=EstadoEvidencia.PENDIENTE
    )

    clave_objeto: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    nombre_original: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confirmada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    eliminada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    eliminada_por_usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Evidencia {self.evidencia_id} orden={self.orden_id} "
            f"contexto={self.contexto} estado={self.estado}>"
        )
