"""SMTP y FCM: configuración, rechazo, aceptación y mensajes sin secretos."""

from uuid import uuid4
import httpx
import pytest
from services.ms1_auth.config import settings
from services.ms1_auth.services import proveedores_notificaciones as p


def test_smtp_externo_no_permite_modo_sin_tls(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_REMITENTE", "taller@example.test")
    monkeypatch.setattr(settings, "SMTP_MODO", "sin_tls_local")
    with pytest.raises(p.SinConfiguracion):
        p.enviar_correo("cliente@example.test", "Aviso", "Mensaje", str(uuid4()))


def test_smtp_acepta_y_conserva_message_id_entre_reintentos(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", 1026)
    monkeypatch.setattr(settings, "SMTP_REMITENTE", "taller@example.test")
    monkeypatch.setattr(settings, "SMTP_MODO", "sin_tls_local")
    monkeypatch.setattr(settings, "SMTP_USUARIO", None)
    monkeypatch.setattr(settings, "SMTP_CLAVE", None)
    mensajes = []

    class SMTP:
        def __init__(self, *args, **kwargs):
            pass

        def send_message(self, mail):
            mensajes.append(mail)
            return {}

        def close(self):
            pass

    monkeypatch.setattr(p.smtplib, "SMTP", SMTP)
    evento = str(uuid4())
    a = p.enviar_correo("cliente@example.test", "Título", "Mensaje", evento)
    b = p.enviar_correo("cliente@example.test", "Título", "Mensaje", evento)
    assert a == b == f"<{evento}@example.test>"
    assert (
        mensajes[0]["To"] == "cliente@example.test" and mensajes[0]["From"] == "taller@example.test"
    )
    assert mensajes[0].get_content().strip() == "Mensaje"


def test_smtp_sin_confirmacion_no_declara_aceptacion(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", 1026)
    monkeypatch.setattr(settings, "SMTP_REMITENTE", "taller@example.test")
    monkeypatch.setattr(settings, "SMTP_MODO", "sin_tls_local")
    monkeypatch.setattr(settings, "SMTP_USUARIO", None)
    monkeypatch.setattr(settings, "SMTP_CLAVE", None)

    class SMTP:
        def __init__(self, *args, **kwargs):
            pass

        def send_message(self, mail):
            raise p.smtplib.SMTPServerDisconnected("Fallo de la conexión")

        def close(self):
            pass

    monkeypatch.setattr(p.smtplib, "SMTP", SMTP)
    with pytest.raises(p.FalloCanal, match="smtp_sin_confirmacion"):
        p.enviar_correo("cliente@example.test", "Aviso", "Mensaje", str(uuid4()))


def test_fcm_requiere_proyecto_y_credencial_del_equipo(monkeypatch):
    monkeypatch.setattr(settings, "FCM_PROJECT_ID", None)
    with pytest.raises(p.SinConfiguracion):
        p.enviar_push("token-dispositivo", "Aviso", "Mensaje", str(uuid4()), 1, 2)


def test_fcm_http_v1_cuerpo_y_aceptacion_no_equivale_a_lectura(monkeypatch):
    monkeypatch.setattr(settings, "FCM_PROJECT_ID", "proyecto-test")
    monkeypatch.setattr(p, "_token_fcm", lambda: "oauth-de-prueba")
    esperado = {}

    def enviar(url, headers, json, timeout):
        esperado.update(url=url, headers=headers, body=json)
        return httpx.Response(200, json={"name": "projects/proyecto-test/messages/1"})

    monkeypatch.setattr(p.httpx, "post", enviar)
    evento = str(uuid4())
    assert (
        p.enviar_push("token-dispositivo", "Aviso", "Mensaje", evento, 8, 9)
        == "projects/proyecto-test/messages/1"
    )
    assert esperado["url"] == "https://fcm.googleapis.com/v1/projects/proyecto-test/messages:send"
    assert esperado["headers"]["Authorization"] == "Bearer oauth-de-prueba"
    assert esperado["body"]["message"]["data"] == {
        "evento_id": evento,
        "orden_id": "8",
        "notificacion_id": "9",
    }


@pytest.mark.parametrize("codigo,desactivar", [("UNREGISTERED", True), ("INVALID_ARGUMENT", False)])
def test_fcm_solo_da_de_baja_un_token_explicitamente_no_registrado(monkeypatch, codigo, desactivar):
    monkeypatch.setattr(settings, "FCM_PROJECT_ID", "proyecto-test")
    monkeypatch.setattr(p, "_token_fcm", lambda: "oauth-de-prueba")
    monkeypatch.setattr(
        p.httpx,
        "post",
        lambda *a, **k: httpx.Response(404, json={"error": {"details": [{"errorCode": codigo}]}}),
    )
    with pytest.raises(p.FalloCanal) as e:
        p.enviar_push("token", "Aviso", "Mensaje", str(uuid4()), 1, 2)
    assert e.value.desactivar_dispositivo == desactivar
