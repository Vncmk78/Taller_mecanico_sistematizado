"""Modelos Rol y UsuarioRol (MS1: Identidad y acceso).

MER (recuadro "BD MS1"):
  ROL(rol_id PK, nombre UK)                 → Cliente / Mecánico / Administrador
  USUARIO_ROL(usuario_id PK/FK, rol_id PK/FK, asignado_en, asignado_por_id FK)

`UsuarioRol` es la tabla puente que implementa los roles múltiples por usuario
(§1.1). Su clave primaria es compuesta (usuario_id, rol_id): un usuario no puede
tener el mismo rol dos veces. Guarda además quién asignó el rol y cuándo, para
trazabilidad. Las tres FK apuntan a tablas de la MISMA base (MS1), por lo que sí
son claves foráneas físicas (a diferencia de las REF entre servicios).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms1_auth.db import Base

if TYPE_CHECKING:
    from services.ms1_auth.models.usuario import Usuario


class Rol(Base):
    __tablename__ = "rol"

    rol_id: Mapped[int] = mapped_column(primary_key=True)
    # Cliente / Mecánico / Administrador. Único: no se repite el nombre de rol.
    nombre: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)

    asignaciones: Mapped[list["UsuarioRol"]] = relationship(
        back_populates="rol",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Rol rol_id={self.rol_id} nombre={self.nombre!r}>"


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    # Clave primaria compuesta: un usuario tiene cada rol a lo más una vez.
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.usuario_id", ondelete="CASCADE"),
        primary_key=True,
    )
    rol_id: Mapped[int] = mapped_column(
        ForeignKey("rol.rol_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    asignado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # Quién asignó el rol (un Usuario administrador). Opcional: puede venir de una
    # carga inicial del sistema. También apunta a usuario, por eso Usuario define
    # `foreign_keys` explícitamente en su relación `roles`.
    asignado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.usuario_id", ondelete="SET NULL"),
        nullable=True,
    )

    usuario: Mapped["Usuario"] = relationship(
        back_populates="roles",
        foreign_keys=[usuario_id],
    )
    rol: Mapped["Rol"] = relationship(back_populates="asignaciones")
    asignado_por: Mapped["Usuario | None"] = relationship(
        foreign_keys=[asignado_por_id],
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UsuarioRol usuario_id={self.usuario_id} rol_id={self.rol_id}>"
