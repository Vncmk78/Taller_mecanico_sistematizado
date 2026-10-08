"""Modelo HistorialRol (MS1: Identidad y acceso).

MER (recuadro "BD MS1"):
  HISTORIAL_ROL(historial_id PK, usuario_id FK, rol_id FK,
                accion: asignado / retirado,
                responsable_id? FK, fecha_hora)

Auditoría de cambios de roles (Semana 4): cada alta o baja de un rol deja una
fila con qué rol cambió, si se asignó o se retiró, quién lo decidió y cuándo.
`usuario_rol` guarda solo el estado vigente; la historia completa —incluidas las
bajas, que borran su fila— vive aquí. Las filas solo se insertan: el historial no
se modifica ni se borra.

- `responsable_id`: el Administrador que hizo el cambio. Queda vacío cuando lo
  hizo el sistema (por ejemplo, el alta inicial de `cliente` en el registro
  público). Apunta a `usuario`, igual que `usuario_rol.asignado_por_id`.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from services.ms1_auth.db import Base


class HistorialRol(Base):
    __tablename__ = "historial_rol"

    __table_args__ = (
        # Consulta típica: "cambios de roles de la cuenta X en orden cronológico".
        Index("ix_historial_rol_usuario_fecha", "usuario_id", "fecha_hora"),
        CheckConstraint(
            "accion in ('asignado', 'retirado')",
            name="accion_valida",
        ),
        CheckConstraint(
            "responsable_id is null or responsable_id > 0",
            name="responsable_positivo",
        ),
    )

    historial_id: Mapped[int] = mapped_column(primary_key=True)
    # Cuenta a la que se le cambió un rol.
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.usuario_id", ondelete="CASCADE"),
        nullable=False,
    )
    rol_id: Mapped[int] = mapped_column(
        ForeignKey("rol.rol_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # 'asignado' al conceder el rol, 'retirado' al quitarlo.
    accion: Mapped[str] = mapped_column(String(10), nullable=False)
    # Quién hizo el cambio. Vacío = lo hizo el sistema.
    responsable_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.usuario_id", ondelete="SET NULL"),
        nullable=True,
    )
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<HistorialRol usuario_id={self.usuario_id} rol_id={self.rol_id} "
            f"accion={self.accion!r}>"
        )
