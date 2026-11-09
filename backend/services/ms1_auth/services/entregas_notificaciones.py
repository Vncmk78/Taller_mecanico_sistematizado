"""Cola persistente de canales: cada aviso lógico conserva sus propios intentos."""

from __future__ import annotations
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from services.ms1_auth.db import SessionLocal
from services.ms1_auth.models.entrega_notificacion import (
    DispositivoPush,
    EntregaNotificacion,
    IntentoEntrega,
)
from services.ms1_auth.models.notificacion import Notificacion
from services.ms1_auth.models.usuario import Usuario


def encolar_canales(db: Session, aviso: Notificacion) -> None:
    """Sin commit: se confirma o revierte junto con el aviso en MS1."""
    db.flush()
    claves = {
        x
        for x in db.scalars(
            select(EntregaNotificacion.clave).where(
                EntregaNotificacion.notificacion_id == aviso.notificacion_id
            )
        )
    }

    def agregar(canal, dispositivo=None, estado="pendiente"):
        clave = f'{canal}:{aviso.evento_id}:{dispositivo or "ninguno"}'
        if clave not in claves:
            db.add(
                EntregaNotificacion(
                    notificacion_id=aviso.notificacion_id,
                    canal=canal,
                    dispositivo_id=dispositivo,
                    clave=clave,
                    estado=estado,
                )
            )

    agregar("correo")
    if aviso.tipo == "stock.alerta":
        return  # Las alertas de stock se dirigen por web y correo (§4.5).
    dispositivos = list(
        db.scalars(
            select(DispositivoPush).where(
                DispositivoPush.usuario_id == aviso.destinatario_id,
                DispositivoPush.activo.is_(True),
            )
        )
    )
    for d in dispositivos:
        agregar("push", d.dispositivo_id)
    if not dispositivos:
        agregar("push", estado="sin_dispositivo")


def registrar_dispositivo(
    db: Session, usuario_id: int, token: str, plataforma: str
) -> tuple[DispositivoPush, bool]:
    clave = hashlib.sha256(token.encode()).hexdigest()
    d = db.scalar(
        select(DispositivoPush).where(DispositivoPush.token_hash == clave).with_for_update()
    )
    creado = d is None
    if d is None:
        d = DispositivoPush(
            usuario_id=usuario_id, token=token, token_hash=clave, plataforma=plataforma
        )
        db.add(d)
    else:
        d.usuario_id = usuario_id
        d.token = token
        d.plataforma = plataforma
        d.activo = True
        d.actualizado_en = datetime.now(timezone.utc)
    db.commit()
    db.refresh(d)
    return d, creado


def procesar_siguiente() -> bool:
    """Reclama un trabajo y su intento antes de tocar la red; no retiene locks SMTP/FCM."""
    from services.ms1_auth.services.proveedores_notificaciones import (
        enviar_correo,
        enviar_push,
        SinConfiguracion,
        FalloCanal,
    )

    ahora = datetime.now(timezone.utc)
    lease = uuid4()
    with SessionLocal() as db:
        e = db.scalar(
            select(EntregaNotificacion)
            .where(
                or_(
                    EntregaNotificacion.estado.in_(["pendiente", "fallida"]),
                    (EntregaNotificacion.estado == "procesando")
                    & (EntregaNotificacion.lease_hasta < ahora),
                ),
                EntregaNotificacion.proxima_tentativa_en <= ahora,
            )
            .order_by(EntregaNotificacion.entrega_id)
            .with_for_update(skip_locked=True)
        )
        if e is None:
            return False
        if e.estado == "procesando":
            anterior = db.scalar(
                select(IntentoEntrega).where(
                    IntentoEntrega.entrega_id == e.entrega_id, IntentoEntrega.numero == e.intentos
                )
            )
            if anterior is not None:
                anterior.resultado = "interrumpida"
                anterior.codigo_error = "lease_expirada"
                anterior.finalizado_en = ahora
        e.estado = "procesando"
        e.intentos += 1
        e.lease_token = lease
        e.lease_hasta = ahora + timedelta(seconds=90)
        intento = IntentoEntrega(entrega_id=e.entrega_id, numero=e.intentos)
        db.add(intento)
        db.flush()
        entrega_id, intento_id = e.entrega_id, intento.intento_id
        n = db.get(Notificacion, e.notificacion_id)
        u = db.get(Usuario, n.destinatario_id)
        d = db.get(DispositivoPush, e.dispositivo_id) if e.dispositivo_id else None
        permitido = (
            u is not None
            and u.activo
            and (
                e.canal == "correo"
                or (d is not None and d.activo and d.usuario_id == n.destinatario_id)
            )
        )
        canal = e.canal
        destino = u.correo if canal == "correo" and u else (d.token if d else "")
        titulo, mensaje, evento, orden, notificacion_id = (
            n.titulo,
            n.mensaje,
            str(n.evento_id),
            n.orden_id,
            n.notificacion_id,
        )
        db.commit()
    estado, codigo, proveedor = "aceptada", None, None
    desactivar = False
    try:
        if not permitido:
            estado, codigo = "omitida", "destinatario_no_disponible"
        elif canal == "correo":
            proveedor = enviar_correo(destino, titulo, mensaje, evento)
        else:
            proveedor = enviar_push(destino, titulo, mensaje, evento, orden, notificacion_id)
    except SinConfiguracion:
        estado, codigo = "sin_configuracion", "proveedor_no_configurado"
    except FalloCanal as exc:
        estado, codigo = "fallida", exc.codigo
        desactivar = exc.desactivar_dispositivo
        if desactivar:
            estado = "omitida"
    except Exception:
        estado, codigo = "fallida", "error_de_canal"  # no persistir secretos del proveedor
    with SessionLocal() as db:
        e = db.scalar(
            select(EntregaNotificacion)
            .where(
                EntregaNotificacion.entrega_id == entrega_id,
                EntregaNotificacion.lease_token == lease,
            )
            .with_for_update()
        )
        if e is None:
            return True  # la concesión venció y otro worker ya la reclamó
        if desactivar and e.dispositivo_id:
            d = db.get(DispositivoPush, e.dispositivo_id)
            if d is not None and d.token == destino:
                d.activo = False
        e.estado = estado
        e.ultimo_error = codigo
        e.proveedor_id = proveedor
        e.lease_token = None
        e.lease_hasta = None
        e.proxima_tentativa_en = datetime.now(timezone.utc) + timedelta(
            seconds=min(3600, 2 ** min(e.intentos, 11))
        )
        if estado == "aceptada":
            e.aceptada_en = datetime.now(timezone.utc)
        intento = db.get(IntentoEntrega, intento_id)
        intento.resultado = estado
        intento.codigo_error = codigo
        intento.finalizado_en = datetime.now(timezone.utc)
        db.commit()
    return True
