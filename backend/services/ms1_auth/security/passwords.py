"""Hash y verificación segura de contraseñas mediante bcrypt."""

from __future__ import annotations

import bcrypt

_MAXIMO_BYTES_BCRYPT = 72


def hash_contrasena(contrasena: str) -> str:
    """Genera un hash bcrypt; la contraseña nunca se persiste en texto plano."""

    contrasena_bytes = contrasena.encode("utf-8")
    if len(contrasena_bytes) > _MAXIMO_BYTES_BCRYPT:
        raise ValueError("La contraseña no puede superar 72 bytes")
    return bcrypt.hashpw(contrasena_bytes, bcrypt.gensalt()).decode("utf-8")


def verificar_contrasena(contrasena: str, contrasena_hash: str) -> bool:
    """Compara una contraseña con su hash sin exponer el valor almacenado."""

    try:
        return bcrypt.checkpw(
            contrasena.encode("utf-8"),
            contrasena_hash.encode("utf-8"),
        )
    except (TypeError, ValueError):
        return False
