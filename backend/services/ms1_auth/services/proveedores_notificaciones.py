"""Adaptadores de canal; aceptar en SMTP/FCM no acredita lectura en el dispositivo."""

from __future__ import annotations
import smtplib
import ssl
from email.message import EmailMessage
import httpx
from services.ms1_auth.config import settings


class SinConfiguracion(Exception):
    pass


class FalloCanal(Exception):
    def __init__(self, codigo: str, *, desactivar_dispositivo=False):
        self.codigo = codigo
        self.desactivar_dispositivo = desactivar_dispositivo
        super().__init__(codigo)


def enviar_correo(destino: str, titulo: str, mensaje: str, evento_id: str) -> str:
    if not settings.SMTP_HOST or not settings.SMTP_REMITENTE:
        raise SinConfiguracion()
    if bool(settings.SMTP_USUARIO) != bool(settings.SMTP_CLAVE):
        raise SinConfiguracion()
    if settings.SMTP_MODO == "sin_tls_local" and settings.SMTP_HOST not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise SinConfiguracion()
    dominio = settings.SMTP_REMITENTE.rsplit("@", 1)[-1]
    if "@" not in settings.SMTP_REMITENTE or "\n" in dominio or "\r" in dominio:
        raise SinConfiguracion()
    ident = f"<{evento_id}@{dominio}>"
    mail = EmailMessage()
    mail["From"] = settings.SMTP_REMITENTE
    mail["To"] = destino
    mail["Subject"] = titulo
    mail["Message-ID"] = ident
    mail.set_content(mensaje)
    conexion = None
    try:
        if settings.SMTP_MODO == "ssl":
            conexion = smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.NOTIFICATION_TIMEOUT_SECONDS,
                context=ssl.create_default_context(),
            )
        else:
            conexion = smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.NOTIFICATION_TIMEOUT_SECONDS,
            )
            if settings.SMTP_MODO == "starttls":
                conexion.starttls(context=ssl.create_default_context())
        if settings.SMTP_USUARIO:
            conexion.login(settings.SMTP_USUARIO, settings.SMTP_CLAVE.get_secret_value())
        rechazados = conexion.send_message(mail)
        if rechazados:
            raise FalloCanal("smtp_destinatario_rechazado")
        return ident
    except smtplib.SMTPAuthenticationError as exc:
        raise FalloCanal("smtp_autenticacion_rechazada") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise FalloCanal("smtp_sin_confirmacion") from exc
    finally:
        # Una falla de QUIT no debe convertir en fallido un DATA ya aceptado.
        if conexion is not None:
            conexion.close()


def _token_fcm() -> str:
    if not settings.FCM_PROJECT_ID or not settings.FCM_CREDENTIALS_FILE:
        raise SinConfiguracion()
    try:
        from google.oauth2.service_account import Credentials
        from google.auth.transport.requests import Request

        credenciales = Credentials.from_service_account_file(
            settings.FCM_CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )

        def solicitar(*args, **kwargs):
            kwargs["timeout"] = settings.NOTIFICATION_TIMEOUT_SECONDS
            return Request()(*args, **kwargs)

        credenciales.refresh(solicitar)
        return credenciales.token
    except (OSError, ValueError, ImportError) as exc:
        raise SinConfiguracion() from exc
    except Exception as exc:
        raise FalloCanal("fcm_autenticacion_no_confirmada") from exc


def enviar_push(
    destino: str, titulo: str, mensaje: str, evento_id: str, orden_id: int, notificacion_id: int
) -> str:
    token = _token_fcm()
    url = f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send"
    payload = {
        "message": {
            "token": destino,
            "notification": {"title": titulo, "body": mensaje},
            "data": {
                "evento_id": evento_id,
                "orden_id": str(orden_id),
                "notificacion_id": str(notificacion_id),
            },
        }
    }
    try:
        r = httpx.post(
            url,
            headers={"Authorization": "Bearer " + token},
            json=payload,
            timeout=settings.NOTIFICATION_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise FalloCanal("fcm_sin_confirmacion") from exc
    try:
        body = r.json()
    except ValueError as exc:
        raise FalloCanal("fcm_respuesta_invalida") from exc
    if r.status_code == 200 and isinstance(body, dict) and isinstance(body.get("name"), str):
        return body["name"][:300]
    error = body.get("error", {}) if isinstance(body, dict) else {}
    detalles = error.get("details", []) if isinstance(error, dict) else []
    no_registrado = any(
        isinstance(d, dict) and d.get("errorCode") == "UNREGISTERED" for d in detalles
    )
    raise FalloCanal(
        "fcm_token_no_registrado" if no_registrado else "fcm_rechazado",
        desactivar_dispositivo=no_registrado,
    )
