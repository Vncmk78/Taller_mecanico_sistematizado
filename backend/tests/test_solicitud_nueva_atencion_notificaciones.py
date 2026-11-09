"""Solicitud confirmada → outbox → avisos propios del personal autorizado."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from services.ms1_auth.config import settings as s1
from services.ms1_auth.main import app as app_ms1
from services.ms1_auth.models import Notificacion, Rol
from services.ms1_auth.models.rol import UsuarioRol
from services.ms2_taller.config import settings as s2
from services.ms2_taller.models import EventoOutbox
from services.ms2_taller.services import publicador_eventos as pub
from test_notificaciones_api import _crear_cliente, _jwt
from test_ordenes_api import api_ordenes, db_ordenes  # noqa: F401
from test_revision_generacion_nueva_atencion_api import _nueva

RUTA='/interno/eventos/nuevas-atenciones/solicitud'
SECRETO='secreto-interno-exclusivo-solicitudes-123456'

def evento():
    return dict(evento_id=str(uuid4()),tipo='nueva_atencion.solicitada',
        ocurrido_en=datetime.now(timezone.utc).isoformat(),solicitud_id=3,
        orden_cancelada_id=4,vehiculo_id=5,cliente_usuario_id=10)

def admin(db, uid, activo=True):
    u=_crear_cliente(db,uid)
    rol=db.scalar(select(Rol).where(Rol.nombre=='administrador'))
    db.add(UsuarioRol(usuario_id=uid,rol_id=rol.rol_id));u.activo=activo;db.commit()

def test_distribuye_solo_al_personal_activo_y_deduplica_por_destinatario(api,db,monkeypatch):
    admin(db,20);admin(db,21);admin(db,22,False);_crear_cliente(db,10)
    monkeypatch.setattr(s1,'EVENT_SHARED_SECRET',SecretStr(SECRETO))
    e=evento();h={'X-Service-Token':SECRETO}
    a=api.post(RUTA,json=e,headers=h);b=api.post(RUTA,json=e,headers=h)
    assert a.status_code==b.status_code==200
    assert a.json()=={'evento_id':e['evento_id'],'creadas':2,'existentes':0}
    assert b.json()=={'evento_id':e['evento_id'],'creadas':0,'existentes':2}
    assert db.scalar(select(func.count()).select_from(Notificacion))==2
    for uid in (20,21):
        n=api.get('/notificaciones',headers={'Authorization':'Bearer '+_jwt(uid)}).json()
        assert len(n)==1 and n[0]['tipo']=='nueva_atencion.solicitada'
        assert 'solicitud n° 3' in n[0]['mensaje'] and n[0]['leida'] is False
    assert api.get('/notificaciones',headers={'Authorization':'Bearer '+_jwt(10)}).json()==[]

@pytest.mark.parametrize('cambio',[{'tipo':'orden.estado_cambiado'},{'solicitud_id':0},{'ocurrido_en':'2026-11-08T10:00:00'},{'destinatario_id':20}])
def test_rechaza_payload_fuera_del_contrato(api,monkeypatch,cambio):
    monkeypatch.setattr(s1,'EVENT_SHARED_SECRET',SecretStr(SECRETO))
    assert api.post(RUTA,json={**evento(),**cambio},headers={'X-Service-Token':SECRETO}).status_code==422

def test_credencial_dedicada_y_fallo_sin_avisos_parciales(api,db,monkeypatch):
    admin(db,20);admin(db,21)
    monkeypatch.setattr(s1,'EVENT_SHARED_SECRET',SecretStr(SECRETO))
    assert api.post(RUTA,json=evento()).status_code==401
    with monkeypatch.context() as p:
        p.setattr(db,'commit',lambda: (_ for _ in ()).throw(SQLAlchemyError('fallo controlado')))
        assert api.post(RUTA,json=evento(),headers={'X-Service-Token':SECRETO}).status_code==500
    assert db.scalar(select(func.count()).select_from(Notificacion))==0


def test_recibo_perdido_reintenta_sin_duplicar_avisos_ni_solicitud(api,db,api_ordenes,db_ordenes,monkeypatch):
    admin(db,20);admin(db,21)
    _,sid=_nueva(api_ordenes,db_ordenes)
    monkeypatch.setattr(s1,'EVENT_SHARED_SECRET',SecretStr(SECRETO))
    monkeypatch.setattr(s2,'EVENT_SHARED_SECRET',SecretStr(SECRETO))
    monkeypatch.setattr(s2,'MS1_URL','http://ms1.test')
    monkeypatch.setattr(pub,'SessionLocal',sessionmaker(db_ordenes.get_bind(),expire_on_commit=False))
    class ReciboPerdido(httpx.AsyncBaseTransport):
        def __init__(self):self.real=httpx.ASGITransport(app=app_ms1);self.primera=True
        async def handle_async_request(self,request):
            assert request.url.path==RUTA
            response=await self.real.handle_async_request(request)
            assert response.status_code==200
            if self.primera:
                self.primera=False
                raise httpx.ReadError('Recibo perdido',request=request)
            return response
    transporte=ReciboPerdido()
    async def enviar():
        async with httpx.AsyncClient(transport=transporte) as c:return await pub.publicar_siguiente_evento(c)
    assert asyncio.run(enviar())
    db_ordenes.expire_all();out=db_ordenes.scalar(select(EventoOutbox))
    assert out.publicado_en is None and out.payload['solicitud_id']==sid
    assert db.scalar(select(func.count()).select_from(Notificacion))==2
    out.proxima_tentativa_en=datetime.now(timezone.utc)-timedelta(seconds=1);db_ordenes.commit()
    assert asyncio.run(enviar())
    db_ordenes.expire_all();out=db_ordenes.scalar(select(EventoOutbox))
    assert out.publicado_en is not None and out.intentos==2
    assert db.scalar(select(func.count()).select_from(Notificacion))==2


def test_fallo_de_outbox_revierte_la_solicitud_completa(api_ordenes,db_ordenes,monkeypatch):
    from services.ms2_taller.models import SolicitudNuevaAtencion
    from test_ordenes_api import _crear_orden, _headers_para
    from shared.auth import NombreRol
    o=_crear_orden(db_ordenes,10,estado_codigo=8)
    flush=db_ordenes.flush
    def fallar_aviso(*args,**kwargs):
        if any(isinstance(x,EventoOutbox) for x in db_ordenes.new):
            raise SQLAlchemyError('No se pudo conservar el evento')
        return flush(*args,**kwargs)
    with monkeypatch.context() as p:
        p.setattr(db_ordenes,'flush',fallar_aviso)
        r=api_ordenes.post(f'/ordenes/{o.orden_id}/nueva-atencion',
            headers=_headers_para(10,NombreRol.CLIENTE),json={'descripcion':'Revisar frenos'})
        assert r.status_code==500
    assert db_ordenes.scalar(select(func.count()).select_from(SolicitudNuevaAtencion))==0
    assert db_ordenes.scalar(select(func.count()).select_from(EventoOutbox))==0
