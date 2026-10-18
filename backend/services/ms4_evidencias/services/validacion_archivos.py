"""Validación de archivos de evidencia antes de subirlos (Semana 6).

Controles del checklist de seguridad (`docs/checklist-seguridad-evidencias.md`):

- 1.1 Lista blanca de formatos: solo `image/jpeg`, `image/png`, `image/webp`,
  `video/mp4` y `video/quicktime`. Cualquier otro tipo responde 415.
- 1.3 Tamaño máximo por tipo: fotos hasta `MS4_MAX_BYTES_FOTO` (10 MiB) y
  videos hasta `MS4_MAX_BYTES_VIDEO` (100 MiB). La lectura se corta apenas se
  supera el límite y responde 413.

Este módulo no conoce la base, el S3 ni FastAPI: recibe la política y el
content_type y lanza excepciones de dominio que el router traduce a HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.ms4_evidencias.config import FORMATOS_SOPORTADOS, Settings
from services.ms4_evidencias.models.evidencia import TipoArchivo


class EvidenciaInvalidaError(ValueError):
    """El archivo o su content_type no constituyen una evidencia válida (422)."""


class TipoArchivoNoPermitidoError(EvidenciaInvalidaError):
    """El formato del archivo no está en la lista blanca (415)."""


class ArchivoDemasiadoGrandeError(EvidenciaInvalidaError):
    """El archivo supera el tamaño máximo de su tipo (413)."""

    def __init__(self, mensaje: str, *, limite_bytes: int) -> None:
        super().__init__(mensaje)
        self.limite_bytes = limite_bytes


MENSAJE_TIPO_NO_PERMITIDO = (
    "Tipo de archivo no permitido. Formatos aceptados: JPG, PNG, WEBP, MP4 y MOV"
)


def normalizar_content_type(content_type: str) -> str:
    """content_type en minúsculas, sin parámetros (``; charset=...``) ni espacios.

    Se rechaza si no tiene la forma ``tipo/subtipo`` o si supera los 100
    caracteres de la columna: así nunca llega a la base un valor que haga fallar
    el INSERT después de haber subido el archivo.
    """
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    tipo, _, subtipo = ct.partition("/")
    if not tipo or not subtipo or len(ct) > 100:
        raise TipoArchivoNoPermitidoError(MENSAJE_TIPO_NO_PERMITIDO)
    return ct


def tipo_desde_content_type(content_type: str) -> TipoArchivo:
    """Clasifica el content_type: image/* es foto, video/* es video."""
    ct = normalizar_content_type(content_type)
    if ct.startswith("image/"):
        return TipoArchivo.FOTO
    if ct.startswith("video/"):
        return TipoArchivo.VIDEO
    raise TipoArchivoNoPermitidoError(MENSAJE_TIPO_NO_PERMITIDO)


def _formatear_mb(cantidad_bytes: int) -> str:
    megas = cantidad_bytes / (1024 * 1024)
    return f"{megas:g} MB" if megas >= 1 else f"{cantidad_bytes} bytes"


@dataclass(frozen=True)
class PoliticaArchivos:
    """Qué formatos se aceptan y cuánto puede pesar cada tipo de archivo."""

    tipos_permitidos: frozenset[str]
    max_bytes_foto: int
    max_bytes_video: int

    @classmethod
    def desde_settings(cls, config: Settings) -> "PoliticaArchivos":
        return cls(
            tipos_permitidos=frozenset(config.TIPOS_PERMITIDOS),
            max_bytes_foto=config.MAX_BYTES_FOTO,
            max_bytes_video=config.MAX_BYTES_VIDEO,
        )

    def validar_tipo(self, content_type: str) -> tuple[str, TipoArchivo]:
        """Normaliza el content_type y exige que esté en la lista blanca (1.1).

        Devuelve el content_type normalizado y si es foto o video. Un tipo
        fuera de la lista (SVG, HTML, PDF, ZIP, ejecutables, GIF, HEIC...) lanza
        `TipoArchivoNoPermitidoError`.
        """
        ct = normalizar_content_type(content_type)
        if ct not in self.tipos_permitidos or ct not in FORMATOS_SOPORTADOS:
            raise TipoArchivoNoPermitidoError(MENSAJE_TIPO_NO_PERMITIDO)
        return ct, tipo_desde_content_type(ct)

    def limite_para(self, tipo: TipoArchivo) -> int:
        """Tamaño máximo en bytes para el tipo de archivo (1.3)."""
        if tipo is TipoArchivo.VIDEO:
            return self.max_bytes_video
        return self.max_bytes_foto

    def error_tamano(self, tipo: TipoArchivo) -> ArchivoDemasiadoGrandeError:
        """Excepción 413 con un mensaje que indica el límite del tipo."""
        limite = self.limite_para(tipo)
        nombre = "El video" if tipo is TipoArchivo.VIDEO else "La foto"
        return ArchivoDemasiadoGrandeError(
            f"{nombre} supera el tamaño máximo permitido ({_formatear_mb(limite)})",
            limite_bytes=limite,
        )
