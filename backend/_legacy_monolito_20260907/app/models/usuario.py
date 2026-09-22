"""Modelo Usuario (con su Rol).

MER: USUARIO(id, nombre, email, password_hash, rol, activo).
Un usuario puede "ser" un Cliente (relación 1:1). La relación con Mecánico se
agregará cuando se cree ese modelo (ticket de otro integrante).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import RolUsuario

if TYPE_CHECKING:
    from app.models.cliente import Cliente


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(
        SAEnum(RolUsuario, name="rol_usuario"),
        nullable=False,
        default=RolUsuario.cliente,
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Un Usuario con rol 'cliente' tiene un registro Cliente asociado.
    cliente: Mapped["Cliente | None"] = relationship(
        back_populates="usuario",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Usuario id={self.id} email={self.email!r} rol={self.rol.value}>"
