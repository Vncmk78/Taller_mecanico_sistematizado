"""Hechos de MS3 duraderos: regla general primero, cruces e idempotencia."""

from datetime import datetime, timezone
from uuid import uuid4
import asyncio
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from pydantic import SecretStr
from services.ms3_presupuestos.models import EventoAvisoOutbox, ParametroInventario, Repuesto
from services.ms3_presupuestos.persistencia import ConflictoDeDatos
from services.ms3_presupuestos.schemas.catalogo import RepuestoActualizar
from services.ms3_presupuestos.schemas.inventario import MovimientoCrear
from services.ms3_presupuestos.services import (
    inventario,
    catalogo,
    presupuestos,
    publicador_avisos as pub,
)
from services.ms3_presupuestos.tests import fabricas
from services.ms3_presupuestos.config import settings


def eventos(db):
    return list(db.scalars(select(EventoAvisoOutbox).order_by(EventoAvisoOutbox.outbox_id)))


def mover(uow, r, cantidad, clave=None):
    return inventario.registrar_movimiento(
        uow,
        MovimientoCrear(
            clave_operacion=clave or str(uuid4()),
            repuesto_id=r.repuesto_id,
            tipo="ajuste",
            cantidad=cantidad,
        ),
        usuario_id=99,
    )


def test_general_primero_activa_particulares_y_cero_cuenta_como_configurado(db, uow):
    assert not db.scalars(select(ParametroInventario)).all()
    r = fabricas.nuevo_repuesto(db, stock=5, umbral_particular=3)
    assert mover(uow, r, -3).alerta.activa is False
    assert inventario.estado_stock(uow, r).umbral_efectivo is None
    assert inventario.alertas(uow) == (None, []) and eventos(db) == []
    inventario.cambiar_umbral_general(uow, valor=0, administrador_id=99, observacion=None)
    assert inventario.estado_stock(uow, r).umbral_efectivo == 3
    assert [e.payload["repuesto_id"] for e in eventos(db)] == [r.repuesto_id]
    assert inventario.alertas(uow)[1][0].repuesto_id == r.repuesto_id
    inventario.cambiar_umbral_general(uow, valor=0, administrador_id=99, observacion=None)
    assert len(eventos(db)) == 1


def test_igualdad_no_alerta_particular_prevalece_y_movimiento_repetido_no_duplica(db, uow):
    fabricas.umbral_general_vigente(db, valor=10)
    r = fabricas.nuevo_repuesto(db, stock=6, umbral_particular=3)
    assert mover(uow, r, -3).alerta.nueva is False  # 3 == 3, aunque general=10
    clave = str(uuid4())
    assert mover(uow, r, -1, clave).alerta.nueva is True
    assert mover(uow, r, -1, clave).repetido is True
    assert mover(uow, r, -1).alerta.nueva is False
    assert len(eventos(db)) == 1
    mover(uow, r, 10)
    assert mover(uow, r, -10).alerta.nueva is True
    assert len(eventos(db)) == 2 and eventos(db)[0].evento_id != eventos(db)[1].evento_id


def test_cambios_de_umbrales_emiten_solo_nuevos_cruces(db, uow):
    fabricas.umbral_general_vigente(db, valor=1)
    r = fabricas.nuevo_repuesto(db, stock=2)
    p = fabricas.nuevo_repuesto(db, stock=2, umbral_particular=1)
    inventario.cambiar_umbral_general(uow, valor=3, administrador_id=99, observacion=None)
    assert [e.payload["repuesto_id"] for e in eventos(db)] == [r.repuesto_id]
    inventario.cambiar_umbral_general(uow, valor=4, administrador_id=99, observacion=None)
    assert len(eventos(db)) == 1
    catalogo.actualizar_repuesto(
        uow, p.repuesto_id, RepuestoActualizar(umbral_particular=None), administrador_id=99
    )
    assert eventos(db)[-1].payload["repuesto_id"] == p.repuesto_id
    catalogo.actualizar_repuesto(
        uow, p.repuesto_id, RepuestoActualizar(nombre="Nombre ajustado"), administrador_id=99
    )
    assert len(eventos(db)) == 2


def test_error_de_outbox_revierte_stock_y_movimiento(db, uow, monkeypatch):
    fabricas.umbral_general_vigente(db, valor=3)
    r = fabricas.nuevo_repuesto(db, stock=4)
    db.commit()
    rid = r.repuesto_id
    with monkeypatch.context() as p:

        def fallar(*a):
            raise SQLAlchemyError("fallo de outbox controlado")

        p.setattr(inventario, "registrar_alerta", fallar)
        with pytest.raises(SQLAlchemyError):
            mover(uow, r, -2)
    assert db.get(Repuesto, rid).stock == 4 and eventos(db) == []


def test_envio_decision_y_eventos_se_confirman_juntos_sin_doble_envio(
    db, uow, presupuesto_borrador
):
    pid = presupuesto_borrador.presupuesto_id
    presupuestos.enviar_version(uow, presupuesto_id=pid, numero=1)
    e = eventos(db)[0]
    assert (
        e.tipo == "presupuesto.enviado" and e.payload["orden_id"] == presupuesto_borrador.orden_id
    )
    with pytest.raises(ConflictoDeDatos):
        presupuestos.enviar_version(uow, presupuesto_id=pid, numero=1)
    presupuestos.decidir_version(
        uow,
        presupuesto_id=pid,
        numero=1,
        cliente_usuario_id=10,
        decision="aprobado",
        motivo=None,
        confirmar_cancelacion=False,
    )
    with pytest.raises(ConflictoDeDatos):
        presupuestos.decidir_version(
            uow,
            presupuesto_id=pid,
            numero=1,
            cliente_usuario_id=10,
            decision="aprobado",
            motivo=None,
            confirmar_cancelacion=False,
        )
    assert [e.tipo for e in eventos(db)] == ["presupuesto.enviado", "presupuesto.decidido"]
    assert eventos(db)[1].payload["decision_id"] > 0


def test_error_al_encolar_revierte_envio_del_presupuesto(
    db, uow, presupuesto_borrador, monkeypatch
):
    pid = presupuesto_borrador.presupuesto_id
    db.commit()
    with monkeypatch.context() as p:

        def fallar(*a, **kw):
            raise SQLAlchemyError("fallo controlado")

        p.setattr(presupuestos, "registrar_hecho", fallar)
        with pytest.raises(SQLAlchemyError):
            presupuestos.enviar_version(uow, presupuesto_id=pid, numero=1)
    assert uow.presupuestos.version(pid, 1).enviado_en is None and eventos(db) == []


def test_publicador_reintenta_mismo_hecho_hasta_recibo_valido(
    db, uow, presupuesto_borrador, monkeypatch
):
    presupuestos.enviar_version(uow, presupuesto_id=presupuesto_borrador.presupuesto_id, numero=1)
    monkeypatch.setattr(
        pub,
        "SessionLocal",
        sessionmaker(
            bind=db.get_bind(), expire_on_commit=False, join_transaction_mode="create_savepoint"
        ),
    )
    monkeypatch.setattr(
        settings, "EVENT_SHARED_SECRET", SecretStr("secreto-exclusivo-avisos-ms3-1234567890")
    )
    recibidos = []

    def destino(req):
        import json

        body = json.loads(req.content)
        recibidos.append(body)
        assert req.headers["X-Service-Token"] == settings.EVENT_SHARED_SECRET.get_secret_value()
        if len(recibidos) == 1:
            raise httpx.ReadError("Respuesta perdida", request=req)
        return httpx.Response(200, json={"evento_id": body["evento_id"]})

    async def enviar():
        async with httpx.AsyncClient(transport=httpx.MockTransport(destino)) as c:
            return await pub.publicar_siguiente(c)

    assert asyncio.run(enviar())
    db.expire_all()
    e = eventos(db)[0]
    assert e.publicado_en is None and e.intentos == 1
    e.proxima_tentativa_en = datetime.now(timezone.utc)
    db.commit()
    assert asyncio.run(enviar())
    db.expire_all()
    e = eventos(db)[0]
    assert e.publicado_en is not None and e.intentos == 2
    assert recibidos[0] == recibidos[1]
    assert not asyncio.run(enviar())
