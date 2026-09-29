"""Prueba mínima: verifica que el hashing de contraseñas funciona (RNF-06)."""
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher


def test_hash_and_verify():
    hasher = BcryptPasswordHasher()
    plain = "SuperClave123!"

    hashed = hasher.hash(plain)

    assert hashed != plain
    assert hasher.verify(plain, hashed) is True
    assert hasher.verify("otra-clave", hashed) is False
