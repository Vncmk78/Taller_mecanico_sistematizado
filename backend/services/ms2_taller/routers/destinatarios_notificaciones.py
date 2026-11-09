"""Consulta interna mínima de MS1: resuelve una referencia lógica, sin PII."""

import hmac
from fastapi import APIRouter, Depends, Header, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from services.ms2_taller.config import settings
from services.ms2_taller.db import get_db
from services.ms2_taller.models import Cliente, OrdenTrabajo, Vehiculo
from shared.contratos_avisos import DestinatarioOrden

router = APIRouter(prefix="/interno/notificaciones", tags=["interno"])


@router.get("/ordenes/{orden_id}/destinatario", response_model=DestinatarioOrden)
def destinatario(
    orden_id: int = Path(gt=0),
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
    db: Session = Depends(get_db),
):
    secreto = settings.NOTIFICATION_LOOKUP_SECRET
    if secreto is None:
        raise HTTPException(status_code=503, detail="Consulta interna no configurada")
    if x_service_token is None or not hmac.compare_digest(
        x_service_token, secreto.get_secret_value()
    ):
        raise HTTPException(status_code=401, detail="Credencial de servicio inválida")
    fila = (
        db.execute(
            select(
                OrdenTrabajo.orden_id,
                OrdenTrabajo.vehiculo_id,
                Cliente.usuario_id.label("cliente_usuario_id"),
            )
            .join(Vehiculo, Vehiculo.vehiculo_id == OrdenTrabajo.vehiculo_id)
            .join(Cliente, Cliente.cliente_id == Vehiculo.cliente_id)
            .where(OrdenTrabajo.orden_id == orden_id)
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return dict(fila)
