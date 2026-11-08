"""Ambiente de pruebas separado: configuración, verificación y ciclo de vida.

Prepara y opera un ambiente local NUEVO, aislado del existente (que usa
`docker-compose.yml` y `.env`), para validar los recorridos con datos sintéticos
reproducibles. No lee, modifica ni elimina nada del ambiente existente.

Aislamiento:
- Infraestructura: `docker-compose.pruebas.yml`, proyecto `sgtm_pruebas`, con
  contenedores, puertos, volúmenes, red y bucket propios. Compose se invoca
  siempre con `-p sgtm_pruebas -f docker-compose.pruebas.yml --env-file .env.pruebas`.
- Configuración: cada proceso hijo recibe `SGTM_ENV_FILE=.env.pruebas` (los
  servicios ya no leen `.env`) y además todas las variables de `.env.pruebas`
  exportadas, que tienen prioridad sobre cualquier archivo.
- Antes de migrar, cargar datos o iniciar procesos se verifica el destino:
  configuración estática (puertos, nombres de bases, bucket, secretos propios,
  valores efectivos de cada servicio) y, con conexión, la marca
  `sgtm-ambiente-pruebas` de cada base y la etiqueta del bucket. Nunca se
  imprimen credenciales.

Uso, desde backend/:
    python scripts/ambiente_pruebas.py configurar     # crea .env.pruebas (una vez)
    python scripts/ambiente_pruebas.py verificar      # solo configuración
    python scripts/ambiente_pruebas.py infra          # levanta PostgreSQL x4 + MinIO
    python scripts/ambiente_pruebas.py verificar --destino
    python scripts/ambiente_pruebas.py migrar         # alembic desde cero, 4 bases
    python scripts/ambiente_pruebas.py iniciar        # gateway, MS1-MS4 y frontend
    python scripts/ambiente_pruebas.py sembrar        # usuarios, catálogo y demo
    python scripts/ambiente_pruebas.py recorridos     # valida los recorridos
    python scripts/ambiente_pruebas.py estado
    python scripts/ambiente_pruebas.py detener        # procesos + contenedores
    python scripts/ambiente_pruebas.py eliminar --confirmar sgtm_pruebas
    python scripts/ambiente_pruebas.py ejecutar -- python scripts/flujos_e2e_gateway.py ...
    python scripts/ambiente_pruebas.py pruebas-ms4    # pruebas reales de MS4 con MinIO
"""
from __future__ import annotations

import argparse
import os
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

BACKEND_DIR = Path(__file__).resolve().parents[1]
RAIZ = BACKEND_DIR.parent
FRONTEND_DIR = RAIZ / "frontend"
ARCHIVO = BACKEND_DIR / ".env.pruebas"
PLANTILLA = BACKEND_DIR / ".env.pruebas.example"
ARCHIVO_EXISTENTE = BACKEND_DIR / ".env"
COMPOSE = BACKEND_DIR / "docker-compose.pruebas.yml"
PROYECTO = "sgtm_pruebas"
EJECUCION = BACKEND_DIR / ".pruebas"  # pids y logs de los procesos (ignorado por Git)
MARCA_BASE = "sgtm-ambiente-pruebas"
ETIQUETA_BUCKET = ("ambiente", "sgtm-pruebas")
BUCKET = "evidencias-pruebas"

PUERTOS_BASES = {"MS1": 5443, "MS2": 5444, "MS3": 5445, "MS4": 5446}
PUERTO_MINIO = 9010
PUERTOS_PROCESOS = {"gateway": 8100, "ms1": 8101, "ms2": 8102, "ms3": 8103, "ms4": 8104}
PUERTO_FRONTEND = 5183
PUERTOS_PERMITIDOS = (
    set(PUERTOS_BASES.values()) | {PUERTO_MINIO, 9011, PUERTO_FRONTEND}
    | set(PUERTOS_PROCESOS.values())
)
# Puertos del ambiente local existente: ningún valor puede apuntar a ellos.
PUERTOS_EXISTENTES = {5433, 5434, 5435, 5436, 9000, 9001, 8000, 8001, 8002, 8003, 8004, 5173}
HOSTS_LOCALES = {"127.0.0.1", "localhost", "::1"}

# URL de servicio esperada por variable (todas obligatorias en .env.pruebas).
URLS_ESPERADAS = {
    "MS2_MS1_URL": 8101,
    "MS2_MS3_URL": 8103,
    "MS3_MS2_URL": 8102,
    "MS4_MS2_URL": 8102,
    "MS4_MS3_URL": 8103,
    "GATEWAY_MS1_URL": 8101,
    "GATEWAY_MS2_URL": 8102,
    "GATEWAY_MS3_URL": 8103,
    "GATEWAY_MS4_URL": 8104,
    "MS4_S3_ENDPOINT": PUERTO_MINIO,
}
OBLIGATORIAS = (
    ["SGTM_AMBIENTE", "PRUEBAS_PG_USUARIO", "PRUEBAS_PG_CLAVE",
     "PRUEBAS_MINIO_ROOT_USUARIO", "PRUEBAS_MINIO_ROOT_CLAVE",
     "MS1_EVENT_SHARED_SECRET", "MS2_EVENT_SHARED_SECRET", "MS2_EVENT_WORKER_ENABLED",
     "GATEWAY_CORS_ORIGINS", "MS4_S3_ACCESS_KEY", "MS4_S3_SECRET_KEY", "MS4_S3_BUCKET"]
    + [f"{s}_DATABASE_URL" for s in PUERTOS_BASES]
    + [f"{s}_JWT_SECRET_KEY" for s in PUERTOS_BASES]
    + list(URLS_ESPERADAS)
)
# Presentes aunque estén vacías (vacío = desactivado de forma explícita).
PRESENTES = ["GATEWAY_CORS_ORIGIN_REGEX"]
# Variables del proceso que cambiarían destinos si se heredaran.
HEREDADAS_PROHIBIDAS = ("VERCEL", "VERCEL_URL", "VERCEL_AUTOMATION_BYPASS_SECRET")


class ErrorAmbiente(Exception):
    """La configuración o el destino no corresponden al ambiente de pruebas."""


# ── configuración ──────────────────────────────────────────────────────────


def leer_archivo(ruta: Path) -> dict[str, str]:
    from dotenv import dotenv_values

    return {k: (v or "") for k, v in dotenv_values(ruta).items()}


def configurar() -> int:
    if ARCHIVO.exists():
        print(f"{ARCHIVO} ya existe; se conservan sus credenciales.")
        return 0
    texto = PLANTILLA.read_text(encoding="utf-8")
    clave_pg = secrets.token_urlsafe(24)
    texto = texto.replace("<PRUEBAS_PG_CLAVE>", clave_pg)
    texto = texto.replace("PRUEBAS_PG_CLAVE=<generar>", f"PRUEBAS_PG_CLAVE={clave_pg}")
    texto = texto.replace("<JWT>", secrets.token_urlsafe(48))
    texto = texto.replace("<EVENTOS>", secrets.token_urlsafe(32))
    while "<generar>" in texto:
        texto = texto.replace("<generar>", secrets.token_urlsafe(24), 1)
    ARCHIVO.write_text(texto, encoding="utf-8")
    try:
        ARCHIVO.chmod(0o600)
    except OSError:
        pass
    print(f"Se creó backend/{ARCHIVO} con secretos propios (no se muestran).")
    return 0


def entorno_pruebas() -> dict[str, str]:
    """Entorno completo para un proceso hijo del ambiente de pruebas."""

    if not ARCHIVO.exists():
        raise ErrorAmbiente("Falta backend/.env.pruebas: ejecutar `configurar` primero")
    valores = leer_archivo(ARCHIVO)
    entorno = {k: v for k, v in os.environ.items() if not _variable_de_servicio(k)}
    entorno.update(valores)
    entorno["SGTM_ENV_FILE"] = str(ARCHIVO)
    for nombre in HEREDADAS_PROHIBIDAS:
        entorno.pop(nombre, None)
    return entorno


def _variable_de_servicio(nombre: str) -> bool:
    # Ninguna variable de servicio heredada de la terminal llega a los hijos:
    # solo valen las de .env.pruebas.
    return nombre.startswith(("MS1_", "MS2_", "MS3_", "MS4_", "GATEWAY_", "MINIO_",
                              "PRUEBAS_", "SGTM_", "APP_TEST_")) or nombre in HEREDADAS_PROHIBIDAS


def _puerto(url: str) -> tuple[str | None, int | None]:
    partes = urlsplit(url)
    return partes.hostname, partes.port


def verificar_configuracion(entorno: dict[str, str]) -> list[str]:
    """Errores de configuración; lista vacía si todo apunta al ambiente nuevo."""

    from sqlalchemy.engine import make_url

    errores: list[str] = []
    if entorno.get("SGTM_AMBIENTE") != "pruebas":
        errores.append("SGTM_AMBIENTE debe ser 'pruebas'")
    for nombre in OBLIGATORIAS:
        if not entorno.get(nombre):
            errores.append(f"{nombre}: falta o está vacía")
    for nombre in PRESENTES:
        if nombre not in entorno:
            errores.append(f"{nombre}: debe estar definida (puede quedar vacía)")
    if any("<" in entorno.get(n, "") for n in OBLIGATORIAS):
        errores.append("Quedan marcadores <...> sin reemplazar en .env.pruebas")

    for servicio, puerto in PUERTOS_BASES.items():
        valor = entorno.get(f"{servicio}_DATABASE_URL", "")
        try:
            url = make_url(valor)
        except Exception:
            errores.append(f"{servicio}_DATABASE_URL: formato inválido")
            continue
        esperado = f"taller_{servicio.lower()}_pruebas"
        if url.host not in HOSTS_LOCALES or url.port != puerto or url.database != esperado:
            errores.append(f"{servicio}_DATABASE_URL debe ser 127.0.0.1:{puerto}/{esperado}")
        if url.username != entorno.get("PRUEBAS_PG_USUARIO"):
            errores.append(f"{servicio}_DATABASE_URL debe usar el usuario PRUEBAS_PG_USUARIO")
        if url.password != entorno.get("PRUEBAS_PG_CLAVE"):
            errores.append(f"{servicio}_DATABASE_URL debe usar la clave PRUEBAS_PG_CLAVE")

    for nombre, puerto in URLS_ESPERADAS.items():
        host, actual = _puerto(entorno.get(nombre, ""))
        if host not in HOSTS_LOCALES or actual != puerto:
            errores.append(f"{nombre} debe apuntar a 127.0.0.1:{puerto}")
    if entorno.get("MS4_S3_BUCKET") != BUCKET:
        errores.append(f"MS4_S3_BUCKET debe ser {BUCKET}")
    publico = entorno.get("MS4_S3_PUBLIC_ENDPOINT")
    if publico and _puerto(publico)[1] != PUERTO_MINIO:
        errores.append(f"MS4_S3_PUBLIC_ENDPOINT debe apuntar al puerto {PUERTO_MINIO}")
    if entorno.get("GATEWAY_CORS_ORIGIN_REGEX"):
        errores.append("GATEWAY_CORS_ORIGIN_REGEX debe quedar vacía en este ambiente")
    for origen in entorno.get("GATEWAY_CORS_ORIGINS", "").split(","):
        if origen.strip() and _puerto(origen.strip())[1] != PUERTO_FRONTEND:
            errores.append(f"GATEWAY_CORS_ORIGINS solo admite el frontend de pruebas ({PUERTO_FRONTEND})")

    jwt = {entorno.get(f"{s}_JWT_SECRET_KEY") for s in PUERTOS_BASES}
    if len(jwt) != 1 or len(next(iter(jwt)) or "") < 32:
        errores.append("Las cuatro *_JWT_SECRET_KEY deben ser iguales y tener al menos 32 caracteres")
    if entorno.get("MS1_EVENT_SHARED_SECRET") != entorno.get("MS2_EVENT_SHARED_SECRET"):
        errores.append("MS1_EVENT_SHARED_SECRET y MS2_EVENT_SHARED_SECRET deben coincidir")

    # Los secretos no pueden ser los del ambiente existente (se compara sin mostrarlos).
    if ARCHIVO_EXISTENTE.exists():
        existente = leer_archivo(ARCHIVO_EXISTENTE)
        for nombre in ("MS1_JWT_SECRET_KEY", "MS1_EVENT_SHARED_SECRET", "MS4_S3_SECRET_KEY"):
            if existente.get(nombre) and existente.get(nombre) == entorno.get(nombre):
                errores.append(f"{nombre} es igual a la del .env existente: usar una propia")

    errores += _verificar_valores_efectivos(entorno)
    return errores


def _verificar_valores_efectivos(entorno: dict[str, str]) -> list[str]:
    """Carga la configuración real de cada servicio en un proceso aparte.

    Así se revisan también los valores por defecto del código (por ejemplo,
    `localhost:8002`) que se usarían si faltara una variable.
    """

    codigo = r"""
import json
from gateway.config import GatewaySettings
from services.ms1_auth.config import Settings as S1
from services.ms2_taller.config import Settings as S2
from services.ms3_presupuestos.config import Settings as S3
from services.ms4_evidencias.config import Settings as S4
salida = {}
for nombre, clase in (("gateway", GatewaySettings), ("ms1", S1), ("ms2", S2), ("ms3", S3), ("ms4", S4)):
    datos = clase().model_dump()
    salida[nombre] = {k: (v.get_secret_value() if hasattr(v, "get_secret_value") else v)
                      for k, v in datos.items()}
print(json.dumps(salida, default=str))
"""
    import json

    resultado = subprocess.run(
        [sys.executable, "-c", codigo], cwd=BACKEND_DIR, env=entorno,
        capture_output=True, text=True, check=False,
    )
    if resultado.returncode != 0:
        # Solo el tipo de error: el detalle de pydantic podría incluir credenciales.
        ultima = resultado.stderr.strip().splitlines()[-1] if resultado.stderr.strip() else ""
        tipo = ultima.split(":", 1)[0][:80] or "sin detalle"
        return [f"No se pudo cargar la configuración efectiva de los servicios ({tipo})"]
    errores: list[str] = []
    for servicio, campos in json.loads(resultado.stdout).items():
        for campo, valor in campos.items():
            for texto in valor if isinstance(valor, list) else [valor]:
                if not isinstance(texto, str) or "://" not in texto:
                    continue
                try:
                    host, puerto = _puerto(texto)
                except ValueError:
                    continue
                if puerto in PUERTOS_EXISTENTES:
                    errores.append(f"{servicio}.{campo} apunta al ambiente existente (puerto {puerto})")
                elif host in HOSTS_LOCALES and puerto not in PUERTOS_PERMITIDOS:
                    errores.append(f"{servicio}.{campo} apunta a un puerto ajeno al ambiente ({puerto})")
                elif host not in HOSTS_LOCALES and host is not None:
                    errores.append(f"{servicio}.{campo} apunta fuera de este equipo")
    return errores


# ── verificación del destino (con conexión) ────────────────────────────────


@dataclass
class Destino:
    nombre: str
    ok: bool
    detalle: str


def verificar_destino(entorno: dict[str, str]) -> list[Destino]:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool

    destinos: list[Destino] = []
    for servicio in PUERTOS_BASES:
        url = make_url(entorno[f"{servicio}_DATABASE_URL"])
        lugar = f"{url.host}:{url.port}/{url.database}"
        try:
            motor = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 5})
            with motor.connect() as conexion:
                base, marca = conexion.execute(text(
                    "select current_database(), shobj_description(oid, 'pg_database') "
                    "from pg_database where datname = current_database()"
                )).one()
            motor.dispose()
        except Exception as exc:  # el mensaje podría incluir credenciales
            destinos.append(Destino(servicio, False, f"{lugar}: sin conexión ({type(exc).__name__})"))
            continue
        if base != url.database or marca != MARCA_BASE:
            destinos.append(Destino(servicio, False,
                                    f"{lugar}: la base no tiene la marca del ambiente de pruebas"))
        else:
            destinos.append(Destino(servicio, True, f"{lugar}: marca {MARCA_BASE}"))

    try:
        import boto3
        from botocore.config import Config as ConfigBoto

        s3 = boto3.client(
            "s3", endpoint_url=entorno["MS4_S3_ENDPOINT"],
            aws_access_key_id=entorno["MS4_S3_ACCESS_KEY"],
            aws_secret_access_key=entorno["MS4_S3_SECRET_KEY"],
            region_name=entorno.get("MS4_S3_REGION") or "us-east-1",
            config=ConfigBoto(signature_version="s3v4", s3={"addressing_style": "path"},
                              connect_timeout=5, retries={"max_attempts": 1}),
        )
        etiquetas = {t["Key"]: t["Value"] for t in s3.get_bucket_tagging(Bucket=BUCKET)["TagSet"]}
        ok = etiquetas.get(ETIQUETA_BUCKET[0]) == ETIQUETA_BUCKET[1]
        destinos.append(Destino("MinIO", ok, f"{_puerto(entorno['MS4_S3_ENDPOINT'])[1]}/{BUCKET}: "
                                + ("etiqueta ambiente=sgtm-pruebas" if ok else "sin la etiqueta del ambiente")))
    except Exception as exc:
        destinos.append(Destino("MinIO", False, f"{BUCKET}: no verificado ({type(exc).__name__})"))
    return destinos


def exigir(entorno: dict[str, str], *, destino: bool) -> None:
    errores = verificar_configuracion(entorno)
    if errores:
        raise ErrorAmbiente("Configuración rechazada:\n  - " + "\n  - ".join(errores))
    print("Configuración: todo apunta al ambiente de pruebas.")
    if destino:
        resultados = verificar_destino(entorno)
        for r in resultados:
            print(f"  {'OK   ' if r.ok else 'FALLA'} {r.nombre}: {r.detalle}")
        if not all(r.ok for r in resultados):
            raise ErrorAmbiente("El destino no es el ambiente de pruebas: no se ejecuta nada.")


# ── Docker Compose (siempre con proyecto y archivo explícitos) ─────────────


def compose(*argumentos: str, entorno: dict[str, str]) -> int:
    comando = ["docker", "compose", "-p", PROYECTO, "-f", str(COMPOSE),
               "--env-file", str(ARCHIVO), *argumentos]
    print("$ " + shlex.join(comando))
    return subprocess.run(comando, cwd=BACKEND_DIR, env=entorno, check=False).returncode


def infra(entorno: dict[str, str]) -> int:
    exigir(entorno, destino=False)
    codigo = compose("up", "-d", "--wait", "db_ms1", "db_ms2", "db_ms3", "db_ms4", "minio",
                     entorno=entorno)
    if codigo == 0:
        codigo = compose("run", "--rm", "minio_init", entorno=entorno)
    return codigo


# ── procesos (gateway, microservicios, frontend) ───────────────────────────


def _pid(nombre: str) -> Path:
    return EJECUCION / f"{nombre}.pid"


def _vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _pid_activo(nombre: str) -> int | None:
    ruta = _pid(nombre)
    if not ruta.exists():
        return None
    pid = int(ruta.read_text().strip() or 0)
    return pid if pid and _vivo(pid) else None


def _puerto_ocupado(puerto: int) -> bool:
    import socket

    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def iniciar(entorno: dict[str, str], *, sin_frontend: bool) -> int:
    exigir(entorno, destino=True)
    EJECUCION.mkdir(exist_ok=True)
    (EJECUCION / "logs").mkdir(exist_ok=True)
    procesos = {
        nombre: [sys.executable, "-m", "uvicorn", modulo, "--host", "127.0.0.1",
                 "--port", str(PUERTOS_PROCESOS[nombre])]
        for nombre, modulo in (
            ("ms1", "services.ms1_auth.main:app"), ("ms2", "services.ms2_taller.main:app"),
            ("ms3", "services.ms3_presupuestos.main:app"),
            ("ms4", "services.ms4_evidencias.main:app"), ("gateway", "gateway.main:app"),
        )
    }
    directorios = dict.fromkeys(procesos, BACKEND_DIR)
    if not sin_frontend:
        npm = shutil.which("npm")
        if npm is None:
            raise ErrorAmbiente("No se encontró npm para iniciar el frontend")
        procesos["frontend"] = [npm, "run", "dev", "--", "--host", "127.0.0.1",
                                "--port", str(PUERTO_FRONTEND), "--strictPort"]
        directorios["frontend"] = FRONTEND_DIR
    entorno_hijo = {**entorno, "SGTM_GATEWAY_URL": f"http://127.0.0.1:{PUERTOS_PROCESOS['gateway']}"}

    for nombre, comando in procesos.items():
        puerto = PUERTOS_PROCESOS.get(nombre, PUERTO_FRONTEND)
        if _pid_activo(nombre):
            print(f"{nombre}: ya está corriendo")
            continue
        if _puerto_ocupado(puerto):
            raise ErrorAmbiente(f"El puerto {puerto} ({nombre}) está ocupado por otro proceso")
        log = open(EJECUCION / "logs" / f"{nombre}.log", "ab")
        proceso = subprocess.Popen(comando, cwd=directorios[nombre], env=entorno_hijo,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        _pid(nombre).write_text(str(proceso.pid))
        print(f"{nombre}: iniciado en 127.0.0.1:{puerto} (log en {EJECUCION / "logs" / f"{nombre}.log"})")
    return _esperar_salud()


def _esperar_salud(segundos: float = 60) -> int:
    import httpx

    limite = time.monotonic() + segundos
    url = f"http://127.0.0.1:{PUERTOS_PROCESOS['gateway']}/api/health/servicios"
    while time.monotonic() < limite:
        try:
            respuesta = httpx.get(url, timeout=3)
            if respuesta.status_code == 200 and respuesta.json().get("status") == "ok":
                print("Gateway de pruebas y sus cuatro microservicios responden.")
                return 0
        except httpx.HTTPError:
            pass
        time.sleep(1)
    print("La Gateway de pruebas no reportó a todos los servicios sanos; revisar backend/.pruebas/logs.")
    return 1


def detener_procesos() -> None:
    for nombre in ("frontend", "gateway", "ms4", "ms3", "ms2", "ms1"):
        pid = _pid_activo(nombre)
        if pid:
            try:
                os.killpg(pid, signal.SIGTERM)
            except OSError:
                os.kill(pid, signal.SIGTERM)
            print(f"{nombre}: detenido")
        _pid(nombre).unlink(missing_ok=True)


def estado(entorno: dict[str, str]) -> int:
    for nombre in ("ms1", "ms2", "ms3", "ms4", "gateway", "frontend"):
        puerto = PUERTOS_PROCESOS.get(nombre, PUERTO_FRONTEND)
        pid = _pid_activo(nombre)
        print(f"{nombre:8} 127.0.0.1:{puerto}  {'corriendo (pid ' + str(pid) + ')' if pid else 'detenido'}")
    return compose("ps", entorno=entorno)


# ── migraciones, datos y recorridos ────────────────────────────────────────


def ejecutar(entorno: dict[str, str], comando: list[str], *, destino: bool = True) -> int:
    exigir(entorno, destino=destino)
    if comando and comando[0] == "--":
        comando = comando[1:]
    if not comando:
        raise ErrorAmbiente("Indicar el comando después de --")
    return subprocess.run(comando, cwd=BACKEND_DIR, env=entorno, check=False).returncode


def migrar(entorno: dict[str, str]) -> int:
    return ejecutar(entorno, [sys.executable, "scripts/migrar.py"])


def sembrar(entorno: dict[str, str]) -> int:
    """Usuarios (MS1/MS2), catálogo base de MS3 y escenarios de demostración (API).

    No usa `seed_datos_ms3.py --integracion`: esa carga escribe en MS3 consumos y
    reservas para órdenes 1 y 2 que MS2 no conoce. Los escenarios con órdenes se
    crean solo a través de la Gateway, con las mismas reglas que la aplicación.
    """

    exigir(entorno, destino=True)
    gateway = f"http://127.0.0.1:{PUERTOS_PROCESOS['gateway']}"

    def correr(paso: list[str]) -> int:
        print(f"$ python {' '.join(paso[1:])}")
        return subprocess.run(paso, cwd=BACKEND_DIR, env=entorno, check=False).returncode

    if codigo := correr([sys.executable, "scripts/seed_usuarios_prueba.py"]):
        return codigo
    ids = _ids_usuarios(entorno, ("administrador@pruebas.cl", "mecanico@pruebas.cl"))
    if codigo := correr([sys.executable, "scripts/seed_datos_ms3.py",
                         "--admin-id", str(ids[0]), "--mecanico-id", str(ids[1])]):
        return codigo
    return correr([sys.executable, "scripts/sembrar_demo_pruebas.py", "--gateway", gateway])


def _ids_usuarios(entorno: dict[str, str], correos: tuple[str, ...]) -> list[int]:
    codigo = (
        "import sys\n"
        "from sqlalchemy import select\n"
        "from services.ms1_auth.db import SessionLocal\n"
        "from services.ms1_auth.models.usuario import Usuario\n"
        "with SessionLocal() as db:\n"
        "    for correo in sys.argv[1:]:\n"
        "        print(db.scalar(select(Usuario.usuario_id).where(Usuario.correo == correo)))\n"
    )
    salida = subprocess.run([sys.executable, "-c", codigo, *correos], cwd=BACKEND_DIR,
                            env=entorno, capture_output=True, text=True, check=True).stdout
    return [int(x) for x in salida.split()]


def recorridos(entorno: dict[str, str], salida: Path | None) -> int:
    gateway = f"http://127.0.0.1:{PUERTOS_PROCESOS['gateway']}"
    comando = [sys.executable, "scripts/verificar_recorridos_pruebas.py", "--gateway", gateway]
    if salida:
        comando += ["--salida", str(salida)]
    return ejecutar(entorno, comando)


# Pruebas de MS4 que usan MinIO real (siempre en buckets exclusivos y desechables).
PRUEBAS_MS4_REALES = (
    "tests/test_ms4_almacenamiento_desechable.py",
    "tests/test_ms4_huerfanos.py",
    "tests/test_ms4_ciclo_archivos.py",
    "tests/test_ms4_minio_integracion.py",
    "tests/test_ms4_recepcion_minio.py",
)


def pruebas_ms4(entorno: dict[str, str], extra: list[str]) -> int:
    """Pruebas reales de MS4 contra el MinIO de este ambiente.

    Cada prueba crea buckets `sgtm-prueba-*` propios y los elimina al terminar;
    nunca usa `evidencias-pruebas` (la demostración) ni el bucket existente. Se
    pasan solo las variables MS4_TEST_*: pytest no recibe la configuración de
    servicios de este ambiente.
    """

    exigir(entorno, destino=True)
    hijo = {k: v for k, v in os.environ.items()
            if not _variable_de_servicio(k) and not k.startswith("MS4_TEST_")}
    hijo.update({
        "MS4_TEST_S3_ENDPOINT": entorno["MS4_S3_ENDPOINT"],
        "MS4_TEST_S3_ADMIN_ACCESS_KEY": entorno["PRUEBAS_MINIO_ROOT_USUARIO"],
        "MS4_TEST_S3_ADMIN_SECRET_KEY": entorno["PRUEBAS_MINIO_ROOT_CLAVE"],
        "MS4_TEST_S3_REGION": entorno.get("MS4_S3_REGION") or "us-east-1",
        "MS4_TEST_S3_MS4_ACCESS_KEY": entorno["MS4_S3_ACCESS_KEY"],
        "MS4_TEST_S3_MS4_SECRET_KEY": entorno["MS4_S3_SECRET_KEY"],
    })
    comando = [sys.executable, "-m", "pytest", "-q", "-rs", *PRUEBAS_MS4_REALES, *extra]
    return subprocess.run(comando, cwd=BACKEND_DIR, env=hijo, check=False).returncode


def eliminar(entorno: dict[str, str], confirmacion: str | None) -> int:
    if confirmacion != PROYECTO:
        print(f"Para eliminar los volúmenes del ambiente de pruebas: --confirmar {PROYECTO}")
        return 2
    detener_procesos()
    # Solo el proyecto sgtm_pruebas: nunca el proyecto ni los volúmenes de docker-compose.yml.
    return compose("down", "--volumes", "--remove-orphans", entorno=entorno)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ambiente de pruebas separado (sgtm_pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    sub.add_parser("configurar")
    p_ver = sub.add_parser("verificar")
    p_ver.add_argument("--destino", action="store_true", help="también conecta y revisa las marcas")
    sub.add_parser("infra")
    sub.add_parser("migrar")
    p_ini = sub.add_parser("iniciar")
    p_ini.add_argument("--sin-frontend", action="store_true")
    sub.add_parser("sembrar")
    p_rec = sub.add_parser("recorridos")
    p_rec.add_argument("--salida", type=Path)
    sub.add_parser("estado")
    sub.add_parser("pruebas-ms4", help="argumentos adicionales se pasan a pytest")
    sub.add_parser("detener")
    p_eli = sub.add_parser("eliminar")
    p_eli.add_argument("--confirmar")
    p_eje = sub.add_parser("ejecutar")
    p_eje.add_argument("comando", nargs=argparse.REMAINDER)
    args, adicionales = parser.parse_known_args()
    if adicionales and args.accion != "pruebas-ms4":
        parser.error("argumentos no reconocidos: " + " ".join(adicionales))

    try:
        if args.accion == "configurar":
            return configurar()
        entorno = entorno_pruebas()
        if args.accion == "verificar":
            exigir(entorno, destino=args.destino)
            return 0
        if args.accion == "infra":
            return infra(entorno)
        if args.accion == "migrar":
            return migrar(entorno)
        if args.accion == "iniciar":
            return iniciar(entorno, sin_frontend=args.sin_frontend)
        if args.accion == "sembrar":
            return sembrar(entorno)
        if args.accion == "pruebas-ms4":
            return pruebas_ms4(entorno, adicionales)
        if args.accion == "recorridos":
            return recorridos(entorno, args.salida)
        if args.accion == "estado":
            return estado(entorno)
        if args.accion == "detener":
            detener_procesos()
            return compose("stop", entorno=entorno)
        if args.accion == "eliminar":
            return eliminar(entorno, args.confirmar)
        if args.accion == "ejecutar":
            return ejecutar(entorno, args.comando)
    except ErrorAmbiente as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
