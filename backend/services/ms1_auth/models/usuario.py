"""Modelo Usuario (MS1: Identidad y acceso).

MER (recuadro "BD MS1"): USUARIO(usuario_id PK, correo UK, nombre,
contrasena_hash, activo, creado_en).

Los roles NO se guardan como columna dentro de Usuario. La Sistematización
final §1.1 define roles múltiples por usuario, así que la relación es N:M a
través de `UsuarioRol` (ver rol.py). Un mismo usuario puede ser, por ejemplo,
Cliente y Mecánico a la vez.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms1_auth.db import Base

if TYPE_CHECKING:
    from services.ms1_auth.models.rol import UsuarioRol


class Usuario(Base):
    __tablename__ = "usuario"

    usuario_id: Mapped[int] = mapped_column(primary_key=True)
    correo: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    contrasena_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Roles asignados a este usuario (N:M vía la tabla puente UsuarioRol).
    # `foreign_keys` es obligatorio: UsuarioRol tiene DOS FK hacia usuario
    # (el titular del rol y quién lo asignó), así que hay que decirle a
    # SQLAlchemy cuál de las dos define esta relación.
    roles: Mapped[list["UsuarioRol"]] = relationship(
        back_populates="usuario",
        foreign_keys="UsuarioRol.usuario_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Usuario usuario_id={self.usuario_id} correo={self.correo!r}>"
