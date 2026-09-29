"""Utilidades de seguridad propias de MS1."""

from services.ms1_auth.security.passwords import hash_contrasena, verificar_contrasena

__all__ = ["hash_contrasena", "verificar_contrasena"]
