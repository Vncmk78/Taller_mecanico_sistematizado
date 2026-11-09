"""Demostración limpia, con recursos diferentes de sgtm_pruebas.

Reutiliza el verificador de destinos y el ciclo de procesos de ambiente_pruebas.
Guarda la configuración generada en backend/.demo-final (ignorada por Git).
No transforma, migra ni elimina las bases anteriores.

Uso: python scripts/demo_final.py configurar|infra|migrar|iniciar|sembrar|estado|detener
"""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import ambiente_pruebas as amb

CARPETA = amb.BACKEND_DIR / ".demo-final"
MARCA = "sgtm-demo-final-v1"
CAMBIOS = {
    "sgtm_pruebas": "sgtm_demo_final",
    "evidencias-pruebas": "evidencias-demo-final",
    "sgtm-pruebas": "sgtm-demo-final",
    "sgtm-ambiente-pruebas": "sgtm-ambiente-demo-final",
    "5443": "5453", "5444": "5454", "5445": "5455", "5446": "5456",
    "8100": "8300", "8101": "8301", "8102": "8302", "8103": "8303", "8104": "8304",
    "9010": "9020", "9011": "9021", "5183": "5383",
}

def transformar(texto: str) -> str:
    for anterior, nuevo in CAMBIOS.items():
        texto = texto.replace(anterior, nuevo)
    return texto


def preparar_perfil() -> None:
    marcador = CARPETA / ".propietario"
    if CARPETA.exists() and (not marcador.exists() or marcador.read_text() != MARCA):
        raise amb.ErrorAmbiente("La carpeta .demo-final existe sin la marca esperada; no se modifica.")
    CARPETA.mkdir(exist_ok=True)
    marcador.write_text(MARCA)
    for carpeta in ("initdb", "minio"):
        destino = CARPETA / carpeta
        destino.mkdir(exist_ok=True)
        origen = amb.BACKEND_DIR / ("pruebas/initdb" if carpeta == "initdb" else "minio")
        for archivo in origen.iterdir():
            if archivo.is_file() and carpeta != "initdb":
                (destino / archivo.name).write_text(transformar(archivo.read_text()))
    # SQL evita ejecutar scripts compartidos desde el filesystem del Mac.
    viejo = CARPETA / "initdb/01-marcar-ambiente.sh"
    if viejo.exists(): viejo.unlink()  # archivo generado por este perfil, nunca el original
    (CARPETA / "initdb/01-marcar-ambiente.sql").write_text(
        "SELECT format('COMMENT ON DATABASE %I IS %L', current_database(), 'sgtm-ambiente-demo-final')\n\\gexec\n")
    plantilla = CARPETA / "env.example"
    plantilla.write_text(transformar(amb.PLANTILLA.read_text()))
    compose = CARPETA / "compose.yml"
    compose.write_text(transformar(amb.COMPOSE.read_text()).replace("./pruebas/initdb:", "./initdb:"))
    contenido = compose.read_text()
    contenido = contenido.replace("\nvolumes:", """
  correo:
    image: axllent/mailpit@sha256:aef2aacc11f075ec0fb6874275ee4a421e688e11a96ebb296134d1735c7761ce
    container_name: sgtm_demo_final_correo
    ports: ["127.0.0.1:1026:1025", "127.0.0.1:8026:8025"]
    environment:
      MP_DATABASE: /data/mailpit.db
      MP_MAX_MESSAGES: 2000
    volumes: [correo:/data]
    labels: {sgtm.ambiente: demo-final}
volumes:
  correo:
    name: sgtm_demo_final_correo
""")
    compose.write_text(contenido)
    ajustes = "\nMS1_NOTIFICATION_WORKER_ENABLED=true\nMS1_SMTP_HOST=127.0.0.1\nMS1_SMTP_PORT=1026\nMS1_SMTP_MODO=sin_tls_local\nMS1_SMTP_REMITENTE=notificaciones@example.test\n"
    if "MS1_SMTP_HOST=" not in plantilla.read_text(): plantilla.write_text(plantilla.read_text()+ajustes)
    privado = CARPETA / ".env"
    if privado.exists() and "MS1_SMTP_HOST=" not in privado.read_text(): privado.write_text(privado.read_text()+ajustes)
    amb.ARCHIVO = CARPETA / ".env"
    amb.PLANTILLA = plantilla
    amb.COMPOSE = compose
    amb.PROYECTO = "sgtm_demo_final"
    amb.EJECUCION = CARPETA / "procesos"
    amb.MARCA_BASE = "sgtm-ambiente-demo-final"
    amb.ETIQUETA_BUCKET = ("ambiente", "sgtm-demo-final")
    amb.BUCKET = "evidencias-demo-final"
    amb.PUERTOS_BASES = {f"MS{i}": 5452+i for i in range(1, 5)}
    amb.PUERTO_MINIO = 9020
    amb.PUERTOS_PROCESOS = {"gateway": 8300, **{f"ms{i}": 8300+i for i in range(1,5)}}
    amb.PUERTO_FRONTEND = 5383
    amb.PUERTOS_PERMITIDOS = set(amb.PUERTOS_BASES.values()) | {8300,8301,8302,8303,8304,5383,9020,9021,1026,8026}
    amb.PUERTOS_EXISTENTES |= {5443,5444,5445,5446,8100,8101,8102,8103,8104,9010,9011,5183}
    amb.URLS_ESPERADAS = {k: int(transformar(str(v))) for k,v in amb.URLS_ESPERADAS.items()}


def main() -> int:
    try:
        preparar_perfil()
        print("Perfil: sgtm_demo_final. Configuración: backend/.demo-final/.env. Web: http://127.0.0.1:5383", flush=True)
        if amb.ARCHIVO.exists():
            amb.completar_configuracion_avisos()
        if sys.argv[1:] == ["infra"]:
            codigo = amb.main()
            if codigo: return codigo
            return amb.compose("up", "-d", "--wait", "correo", entorno=amb.entorno_pruebas())
        if sys.argv[1:] == ["sembrar"]:
            codigo = amb.main()
            if codigo: return codigo
            entorno = amb.entorno_pruebas()
            amb.exigir(entorno, destino=True)
            return subprocess.run([sys.executable, str(amb.BACKEND_DIR / "scripts/sembrar_nuevas_atenciones_demo.py"),
                "--gateway", "http://127.0.0.1:8300"], cwd=amb.BACKEND_DIR, env=entorno, check=False).returncode
        return amb.main()
    except amb.ErrorAmbiente as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
