"""Validación de archivos de evidencia antes de subirlos (Semana 6).

Controles del checklist de seguridad (`docs/checklist-seguridad-evidencias.md`):

- 1.1 Lista blanca de formatos: solo `image/jpeg`, `image/png`, `image/webp`,
  `video/mp4` y `video/quicktime`. Cualquier otro tipo responde 415.
- 1.2 El tipo se valida por el contenido: se leen los primeros bytes (firma o
  *magic bytes*) y deben corresponder al formato declarado. Un HTML renombrado
  a `.jpg` o un PNG enviado como `image/jpeg` responde 415.
- 1.3 Tamaño máximo por tipo: fotos hasta `MS4_MAX_BYTES_FOTO` (10 MiB) y
  videos hasta `MS4_MAX_BYTES_VIDEO` (100 MiB). La lectura se corta apenas se
  supera el límite y responde 413.
- 1.6 Archivo vacío o dañado: 0 bytes, o una estructura incompleta (JPEG sin
  marcador de fin, PNG sin IEND, WEBP o MP4/MOV truncados) responde 422.

Este módulo no conoce la base, el S3 ni FastAPI: recibe la política y el
content_type y lanza excepciones de dominio que el router traduce a HTTP.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import BinaryIO

from services.ms4_evidencias.config import FORMATOS_SOPORTADOS, Settings
from services.ms4_evidencias.models.evidencia import TipoArchivo


class EvidenciaInvalidaError(ValueError):
    """El archivo o su content_type no constituyen una evidencia válida (422)."""


class TipoArchivoNoPermitidoError(EvidenciaInvalidaError):
    """El formato del archivo no está en la lista blanca (415)."""


class ContenidoNoCoincideError(TipoArchivoNoPermitidoError):
    """Los bytes del archivo no corresponden al formato declarado (415)."""


class ArchivoDanadoError(EvidenciaInvalidaError):
    """El archivo tiene la firma correcta pero está incompleto o dañado (422)."""


class ArchivoIlegibleError(EvidenciaInvalidaError):
    """No se pudo leer el archivo recibido (temporal ilegible o cerrado) (400)."""


class ArchivoDemasiadoGrandeError(EvidenciaInvalidaError):
    """El archivo supera el tamaño máximo de su tipo (413)."""

    def __init__(self, mensaje: str, *, limite_bytes: int) -> None:
        super().__init__(mensaje)
        self.limite_bytes = limite_bytes


MENSAJE_TIPO_NO_PERMITIDO = (
    "Tipo de archivo no permitido. Formatos aceptados: JPG, PNG, WEBP, MP4 y MOV"
)

MENSAJE_CONTENIDO_NO_COINCIDE = (
    "El contenido del archivo no corresponde al formato declarado"
)
MENSAJE_ARCHIVO_DANADO = "El archivo está dañado o incompleto"
MENSAJE_ARCHIVO_ILEGIBLE = "No se pudo leer el archivo enviado"


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


# --------------------------------------------------------------------------- #
# Validación por contenido (checklist 1.2 y 1.6)                              #
# --------------------------------------------------------------------------- #

# Bytes necesarios para reconocer cualquiera de los formatos soportados.
TAMANO_CABECERA = 16

# Marcas (brands) ISO BMFF que son imágenes, no video: HEIC/HEIF/AVIF también
# empiezan con una caja `ftyp`, pero no están en la lista blanca.
_MARCAS_IMAGEN = frozenset(
    {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"mif1", b"msf1",
     b"avif", b"avis"}
)
# Átomos con los que empieza un MOV antiguo que no trae `ftyp`.
_ATOMOS_INICIO_MOV = frozenset({b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot"})
# MP4 y MOV comparten estructura y los navegadores los reportan indistintamente
# (un .mov de iPhone puede llegar como video/mp4 y viceversa).
_EQUIVALENTES = {"video/mp4": "video/quicktime", "video/quicktime": "video/mp4"}

_FIN_JPEG = b"\xff\xd9"
_FIN_PNG = b"IEND\xaeB`\x82"
_BLOQUE_LECTURA = 1024 * 1024


def detectar_formato(cabecera: bytes) -> str | None:
    """content_type real según los primeros bytes, o None si no se reconoce.

    Solo reconoce los formatos soportados por MS4; cualquier otra firma
    (HTML, SVG, PDF, ZIP, ejecutables, GIF, HEIC...) devuelve None.
    """
    if cabecera.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if cabecera.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return "image/webp"
    tipo_caja = cabecera[4:8]
    if tipo_caja == b"ftyp":
        marca = cabecera[8:12]
        if marca in _MARCAS_IMAGEN:
            return None
        return "video/quicktime" if marca == b"qt  " else "video/mp4"
    if tipo_caja in _ATOMOS_INICIO_MOV:
        return "video/quicktime"
    return None


def _contiene(archivo: BinaryIO, patron: bytes, desde: int) -> bool:
    """True si `patron` aparece en el archivo a partir del byte `desde`.

    Lee en bloques de 1 MiB y conserva el final del bloque anterior para no
    perder un patrón partido entre dos bloques.
    """
    archivo.seek(desde)
    arrastre = b""
    while True:
        bloque = archivo.read(_BLOQUE_LECTURA)
        if not bloque:
            return False
        if patron in arrastre + bloque:
            return True
        arrastre = (arrastre + bloque)[-(len(patron) - 1):]


def _webp_completo(archivo: BinaryIO, tamano: int) -> bool:
    """El tamaño declarado en la cabecera RIFF no puede superar al real."""
    archivo.seek(4)
    declarado = struct.unpack("<I", archivo.read(4))[0]
    return tamano >= 12 and declarado + 8 <= tamano


def _iso_bmff_completo(archivo: BinaryIO, tamano: int) -> bool:
    """Recorre las cajas de primer nivel de un MP4/MOV.

    Cada caja debe caber dentro del archivo (un video cortado a la mitad deja
    la última caja "colgando") y debe existir la caja `moov`, que describe las
    pistas: sin ella el video no se puede reproducir.
    """
    posicion = 0
    tiene_moov = False
    while posicion < tamano:
        archivo.seek(posicion)
        cabecera = archivo.read(8)
        if len(cabecera) < 8:
            return False
        tamano_caja, tipo_caja = struct.unpack(">I4s", cabecera)
        largo_cabecera = 8
        if tamano_caja == 1:  # tamaño extendido de 64 bits
            extendido = archivo.read(8)
            if len(extendido) < 8:
                return False
            tamano_caja = struct.unpack(">Q", extendido)[0]
            largo_cabecera = 16
        elif tamano_caja == 0:  # la caja llega hasta el final del archivo
            tamano_caja = tamano - posicion
        if tamano_caja < largo_cabecera or posicion + tamano_caja > tamano:
            return False
        tiene_moov = tiene_moov or tipo_caja == b"moov"
        posicion += tamano_caja
    return tiene_moov


def _estructura_completa(archivo: BinaryIO, formato: str, tamano: int) -> bool:
    if formato == "image/jpeg":
        return _contiene(archivo, _FIN_JPEG, desde=3)
    if formato == "image/png":
        return _contiene(archivo, _FIN_PNG, desde=8)
    if formato == "image/webp":
        return _webp_completo(archivo, tamano)
    return _iso_bmff_completo(archivo, tamano)


def validar_contenido(
    archivo: BinaryIO,
    content_type_declarado: str,
    tamano: int,
    politica: PoliticaArchivos,
) -> str:
    """Comprueba que los bytes correspondan al formato declarado (1.2 y 1.6).

    1. Lee la cabecera y detecta el formato real. Si no se reconoce o no está
       en la lista blanca → `ContenidoNoCoincideError` (415).
    2. Si no coincide con el declarado → `ContenidoNoCoincideError` (415).
       Excepción: MP4 y MOV son intercambiables (misma estructura).
    3. Revisa que la estructura esté completa → `ArchivoDanadoError` (422).

    Devuelve el content_type detectado, que es el que se guarda y con el que
    se firma la descarga (control 3.4: tipo definido por el servidor). Deja el
    archivo al inicio.
    """
    try:
        archivo.seek(0)
        formato = detectar_formato(archivo.read(TAMANO_CABECERA))
        if formato is None or formato not in politica.tipos_permitidos:
            raise ContenidoNoCoincideError(MENSAJE_CONTENIDO_NO_COINCIDE)
        if formato != content_type_declarado and _EQUIVALENTES.get(formato) != (
            content_type_declarado
        ):
            raise ContenidoNoCoincideError(MENSAJE_CONTENIDO_NO_COINCIDE)
        if not _estructura_completa(archivo, formato, tamano):
            raise ArchivoDanadoError(MENSAJE_ARCHIVO_DANADO)
        return formato
    finally:
        archivo.seek(0)
