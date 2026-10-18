"""Archivos mínimos y estructuralmente válidos para las pruebas de MS4.

Cada función arma, en memoria, un archivo con la firma (magic bytes) y la
estructura mínima de su formato, rellenado hasta `tamano` bytes. Así las
pruebas de lista blanca, tamaño máximo y validación por contenido (Semana 6)
usan archivos que se parecen a los reales sin depender de imágenes guardadas
en el repositorio.
"""
from __future__ import annotations

import struct
import zlib

FIRMA_PNG = b"\x89PNG\r\n\x1a\n"


def _caja(tipo: bytes, contenido: bytes = b"") -> bytes:
    """Caja (atom) ISO BMFF: tamaño de 32 bits + tipo de 4 bytes + contenido."""
    return struct.pack(">I", 8 + len(contenido)) + tipo + contenido


def _chunk_png(tipo: bytes, datos: bytes) -> bytes:
    crc = zlib.crc32(tipo + datos) & 0xFFFFFFFF
    return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", crc)


def jpeg(tamano: int = 2048) -> bytes:
    """JPEG: SOI + APP0 (JFIF) + relleno + EOI."""
    inicio = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    fin = b"\xff\xd9"
    relleno = max(tamano - len(inicio) - len(fin), 0)
    return inicio + b"\x00" * relleno + fin


def jpeg_con(contenido: bytes) -> bytes:
    """JPEG con `contenido` propio entre la cabecera y el fin (bytes únicos)."""
    return jpeg(0)[:-2] + contenido + b"\xff\xd9"


def png(tamano: int = 2048) -> bytes:
    """PNG: firma + IHDR + tEXt de relleno + IEND."""
    ihdr = _chunk_png(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    iend = _chunk_png(b"IEND", b"")
    fijo = len(FIRMA_PNG) + len(ihdr) + len(iend) + 12  # 12 = cabecera+crc de tEXt
    texto = _chunk_png(b"tEXt", b"x" * max(tamano - fijo, 0))
    return FIRMA_PNG + ihdr + texto + iend


def webp(tamano: int = 2048) -> bytes:
    """WEBP: RIFF + tamaño coherente + 'WEBP' + chunk VP8 de relleno."""
    tamano = max(tamano, 20)
    cuerpo = b"WEBP" + b"VP8 " + struct.pack("<I", tamano - 20) + b"\x00" * (tamano - 20)
    return b"RIFF" + struct.pack("<I", len(cuerpo)) + cuerpo


def _iso_bmff(marca: bytes, tamano: int) -> bytes:
    ftyp = _caja(b"ftyp", marca + struct.pack(">I", 0x200) + marca + b"mp41")
    moov = _caja(b"moov", _caja(b"mvhd", b"\x00" * 100))
    relleno = max(tamano - len(ftyp) - len(moov) - 8, 0)
    return ftyp + moov + _caja(b"mdat", b"\x00" * relleno)


def mp4(tamano: int = 4096) -> bytes:
    """MP4: ftyp (isom) + moov + mdat de relleno."""
    return _iso_bmff(b"isom", tamano)


def mov(tamano: int = 4096) -> bytes:
    """MOV (QuickTime): ftyp con marca 'qt  ' + moov + mdat de relleno."""
    return _iso_bmff(b"qt  ", tamano)


# content_type → función que genera un archivo válido de ese formato.
POR_CONTENT_TYPE = {
    "image/jpeg": jpeg,
    "image/png": png,
    "image/webp": webp,
    "video/mp4": mp4,
    "video/quicktime": mov,
}

# Foto JPEG pequeña y válida, por defecto en las pruebas de subida.
JPEG_VALIDO = jpeg_con(b"datos-de-foto")
