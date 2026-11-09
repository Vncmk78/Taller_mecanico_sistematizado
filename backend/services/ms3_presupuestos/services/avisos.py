"""Registro transaccional de hechos de presupuesto e inventario para MS1."""

from datetime import timezone
from uuid import uuid4
from pydantic import TypeAdapter
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.models import Repuesto
from sqlalchemy import func, select
from shared.contratos_avisos import AvisoMS3
from services.ms3_presupuestos.models.evento_aviso_outbox import EventoAvisoOutbox

_ADAPTADOR = TypeAdapter(AvisoMS3)


def registrar_hecho(uow: UnidadDeTrabajo, tipo: str, **datos) -> None:
    ahora = uow.sesion.scalar(select(func.now()))
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
    evento = _ADAPTADOR.validate_python(
        dict(evento_id=uuid4(), tipo=tipo, ocurrido_en=ahora, **datos)
    )
    uow.sesion.add(
        EventoAvisoOutbox(
            evento_id=evento.evento_id, tipo=tipo, payload=evento.model_dump(mode="json")
        )
    )


def registrar_alerta(uow: UnidadDeTrabajo, repuesto: Repuesto, umbral: int) -> None:
    registrar_hecho(
        uow,
        "stock.alerta",
        repuesto_id=repuesto.repuesto_id,
        nombre=repuesto.nombre,
        stock=repuesto.stock,
        umbral=umbral,
    )
