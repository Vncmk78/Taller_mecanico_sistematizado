"""Inicializa las cuatro bases de SGTM y aplica sus migraciones en orden.

Pasos (se detiene en el primero que falla; nada se modifica antes del paso 5):
  1. Configuración: DSN explícitos postgresql+psycopg, una base distinta por
     servicio y, en el perfil `despliegue`, sin claves de ejemplo.
  2. Conexión: espera a que las cuatro bases respondan (reintentos).
  3. Permisos: PostgreSQL >= 13, el rol puede crear en `public` y MS3 dispone
     de las extensiones pg_trgm y unaccent.
  4. Estado previo: revisión de cada base frente a los heads del código.
  5. Migración: MS1 → MS2 → MS3 → MS4, cada una con un candado consultivo para
     que dos procesos (dos réplicas, dos personas) no migren a la vez.
  6. Verificación: heads aplicados y todas las tablas de los modelos presentes.

Uso (desde cualquier carpeta; lee backend/.env o el archivo de SGTM_ENV_FILE,
y las variables del proceso tienen prioridad):
  python scripts/inicializar_bd.py                     # pasos 1 a 6
  python scripts/inicializar_bd.py verificar           # pasos 1-4 y 6, sin escribir
  python scripts/inicializar_bd.py configurar          # crea despliegue/.env.despliegue
  python scripts/inicializar_bd.py --perfil local      # admite claves de desarrollo

Códigos de salida: 0 correcto; 1 configuración, conexión o permisos (no se
modificó nada); 2 fallo al migrar o en la verificación final.
No crea bases ni roles (eso lo hace despliegue/initdb o el panel del
proveedor), no carga datos y no hace downgrade. No imprime DSN ni claves.
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from shared.entorno import ruta_entorno  # noqa: E402

ORDEN = ("MS1", "MS2", "MS3", "MS4")
PAQUETES = {
    "MS1": "ms1_auth",
    "MS2": "ms2_taller",
    "MS3": "ms3_presupuestos",
    "MS4": "ms4_evidencias",
}
# Extensiones que crean las migraciones (deben estar disponibles en el servidor).
EXTENSIONES = {"MS3": ("pg_trgm", "unaccent")}
# Claves de ejemplo o de desarrollo que nunca deben llegar a un despliegue.
CLAVES_DEBILES = {
    "", "taller", "postgres", "password", "admin", "123456", "changeme",
    "cambia-esta-clave", "cambia-esta-clave-local", "__generar__",
}
SSLMODES_SEGUROS = {"require", "verify-ca", "verify-full"}
# Clave del candado consultivo ('SGTM' en ASCII): igual en las cuatro bases.
CANDADO = 0x5347544D
VERSION_MINIMA = 130000  # extensiones "trusted" para el dueño de la base

PLANTILLA = BACKEND_DIR / "despliegue" / "env.despliegue.example"
ARCHIVO_DESPLIEGUE = BACKEND_DIR / "despliegue" / ".env.despliegue"


class ErrorPaso(Exception):
    """Fallo controlado de un paso; el mensaje nunca contiene credenciales."""

    def __init__(self, mensaje: str, codigo: int = 1) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


@dataclass
class Base:
    servicio: str
    url: URL
    avisos: list[str] = field(default_factory=list)

    @property
    def destino(self) -> str:
        return f"{self.url.host}:{self.url.port or 5432}/{self.url.database}"


# ── entorno ────────────────────────────────────────────────────────────────


def cargar_entorno() -> dict[str, str]:
    """Variables del archivo de entorno + las del proceso (con prioridad).

    Se exportan al proceso para que la configuración de cada servicio (que se
    importa al migrar) lea exactamente los mismos valores.
    """

    archivo = ruta_entorno(BACKEND_DIR)
    valores = {k: v for k, v in dotenv_values(archivo).items() if v is not None}
    for clave, valor in valores.items():
        os.environ.setdefault(clave, valor)
    return {**valores, **os.environ}


# ── paso 1: configuración ──────────────────────────────────────────────────


def validar_configuracion(entorno: dict[str, str], *, perfil: str, exigir_tls: bool) -> list[Base]:
    errores: list[str] = []
    bases: list[Base] = []
    for servicio in ORDEN:
        dsn = entorno.get(f"{servicio}_DATABASE_URL", "")
        if not dsn:
            errores.append(f"{servicio}: falta {servicio}_DATABASE_URL")
            continue
        try:
            url = make_url(dsn)
        except Exception:
            errores.append(f"{servicio}: {servicio}_DATABASE_URL no es una URL válida")
            continue
        if url.drivername != "postgresql+psycopg":
            errores.append(f"{servicio}: se requiere postgresql+psycopg:// (hay {url.drivername}://)")
            continue
        if not url.host or not url.database or not url.username:
            errores.append(f"{servicio}: la URL debe indicar usuario, host y base")
            continue
        base = Base(servicio, url)
        clave = (url.password or "").lower()
        if clave in CLAVES_DEBILES or len(clave) < 12:
            mensaje = f"{servicio}: clave de base vacía, de ejemplo o con menos de 12 caracteres"
            (errores if perfil == "despliegue" else base.avisos).append(mensaje)
        if url.username in {"postgres", "taller"}:
            mensaje = f"{servicio}: usa el rol '{url.username}'; en despliegue cada servicio usa su propio rol"
            (errores if perfil == "despliegue" else base.avisos).append(mensaje)
        sslmode = url.query.get("sslmode")
        if exigir_tls and sslmode not in SSLMODES_SEGUROS:
            errores.append(f"{servicio}: --exigir-tls requiere sslmode=require|verify-ca|verify-full")
        bases.append(base)

    destinos: dict[tuple, list[str]] = {}
    for base in bases:
        destinos.setdefault((base.url.host, base.url.port or 5432, base.url.database), []).append(base.servicio)
    for servicios in destinos.values():
        if len(servicios) > 1:
            errores.append(f"{' y '.join(servicios)} apuntan a la misma base; cada servicio necesita la suya")
    usuarios: dict[tuple, list[str]] = {}
    for base in bases:
        usuarios.setdefault((base.url.host, base.url.port or 5432, base.url.username), []).append(base.servicio)
    for servicios in usuarios.values():
        if len(servicios) > 1:
            for base in bases:
                if base.servicio in servicios:
                    base.avisos.append(f"comparte rol con {', '.join(s for s in servicios if s != base.servicio)}")
    if errores:
        raise ErrorPaso("\n".join(f"  - {e}" for e in errores))
    return bases


# ── paso 2 y 3: conexión y permisos ────────────────────────────────────────


def _engine(base: Base) -> Engine:
    return create_engine(base.url, poolclass=NullPool, connect_args={"connect_timeout": 5})


def esperar_conexion(bases: list[Base], *, segundos: float) -> None:
    pendientes = {b.servicio: b for b in bases}
    limite = time.monotonic() + segundos
    espera = 1.0
    ultimo: dict[str, str] = {}
    while pendientes:
        for servicio, base in list(pendientes.items()):
            engine = _engine(base)
            try:
                with engine.connect() as conexion:
                    conexion.exec_driver_sql("SELECT 1")
                del pendientes[servicio]
            except Exception as exc:  # el texto puede traer el DSN: solo el tipo
                ultimo[servicio] = type(exc).__name__
            finally:
                engine.dispose()
        if not pendientes:
            return
        if time.monotonic() >= limite:
            detalle = ", ".join(f"{s} ({pendientes[s].destino}: {ultimo[s]})" for s in pendientes)
            raise ErrorPaso(f"  - sin respuesta después de {segundos:.0f} s: {detalle}")
        time.sleep(espera)
        espera = min(espera * 2, 5)


def revisar_permisos(bases: list[Base]) -> None:
    errores: list[str] = []
    for base in bases:
        engine = _engine(base)
        try:
            with engine.connect() as conexion:
                version = int(conexion.exec_driver_sql("SHOW server_version_num").scalar())
                if version < VERSION_MINIMA:
                    errores.append(f"{base.servicio}: PostgreSQL {version} < 13")
                fila = conexion.execute(text(
                    "SELECT has_schema_privilege(current_user, 'public', 'CREATE') AS crear,"
                    " r.rolsuper AS super,"
                    " pg_get_userbyid(d.datdba) = current_user AS duenio"
                    " FROM pg_roles r, pg_database d"
                    " WHERE r.rolname = current_user AND d.datname = current_database()"
                )).one()
                if not fila.crear:
                    errores.append(f"{base.servicio}: el rol no puede crear tablas en public")
                if fila.super:
                    base.avisos.append("el rol es superusuario; en despliegue usar un rol sin privilegios")
                if not fila.duenio:
                    base.avisos.append("el rol no es dueño de la base (las extensiones pueden fallar)")
                for extension in EXTENSIONES.get(base.servicio, ()):
                    disponible = conexion.execute(
                        text("SELECT 1 FROM pg_available_extensions WHERE name = :n"), {"n": extension}
                    ).first()
                    if not disponible:
                        errores.append(f"{base.servicio}: la extensión {extension} no está disponible")
        except ErrorPaso:
            raise
        except Exception as exc:
            errores.append(f"{base.servicio}: no se pudieron revisar permisos ({type(exc).__name__})")
        finally:
            engine.dispose()
    if errores:
        raise ErrorPaso("\n".join(f"  - {e}" for e in errores))


# ── pasos 4 a 6: estado, migración y verificación ──────────────────────────


def estado_revisiones():
    from scripts.verificar_migraciones import verificar_todas

    return verificar_todas()


def mostrar_estado(resultados) -> int:
    from scripts.verificar_migraciones import mostrar

    return mostrar(resultados)


def _tomar_candado(base: Base, segundos: float):
    engine = _engine(base)
    conexion = engine.connect()
    limite = time.monotonic() + segundos
    while True:
        if conexion.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": CANDADO}).scalar():
            conexion.commit()
            return engine, conexion
        conexion.rollback()
        if time.monotonic() >= limite:
            conexion.close()
            engine.dispose()
            raise ErrorPaso(f"  - {base.servicio}: otro proceso está migrando esta base (candado ocupado)")
        time.sleep(1)


def migrar_en_orden(bases: list[Base], *, espera_candado: float = 120) -> list[tuple[str, float]]:
    from alembic import command

    from scripts.verificar_migraciones import configuracion

    tiempos: list[tuple[str, float]] = []
    for base in bases:
        inicio = time.monotonic()
        engine, conexion = _tomar_candado(base, espera_candado)
        try:
            print(f"    {base.servicio} → heads ({base.destino})", flush=True)
            command.upgrade(configuracion(base.servicio), "heads")
        except Exception as exc:
            raise ErrorPaso(
                f"  - {base.servicio}: la migración falló ({type(exc).__name__}). "
                "Los servicios anteriores ya quedaron migrados; corregir y volver a ejecutar.",
                codigo=2,
            ) from exc
        finally:
            try:
                conexion.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": CANDADO})
                conexion.commit()
            finally:
                conexion.close()
                engine.dispose()
        tiempos.append((base.servicio, time.monotonic() - inicio))
        print(f"    {base.servicio}: listo en {tiempos[-1][1]:.1f} s", flush=True)
    return tiempos


def tablas_faltantes(base: Base) -> list[str]:
    import importlib

    paquete = PAQUETES[base.servicio]
    modulo_db = importlib.import_module(f"services.{paquete}.db")
    importlib.import_module(f"services.{paquete}.models")
    esperadas = {t.name for t in modulo_db.Base.metadata.sorted_tables}
    engine = _engine(base)
    try:
        with engine.connect() as conexion:
            presentes = set(inspect(conexion).get_table_names())
    finally:
        engine.dispose()
    return sorted(esperadas - presentes)


def verificacion_final(bases: list[Base]) -> int:
    resultados = estado_revisiones()
    codigo = mostrar_estado(resultados)
    al_dia = {r.servicio for r in resultados if r.estado == "OK"}
    for base in bases:
        if base.servicio not in al_dia:
            continue  # sin migrar: faltan tablas por definición
        faltan = tablas_faltantes(base)
        if faltan:
            print(f"  - {base.servicio}: faltan tablas del modelo: {', '.join(faltan)}")
            codigo = 2
    return codigo


# ── configurar ─────────────────────────────────────────────────────────────


def configurar(destino: Path = ARCHIVO_DESPLIEGUE) -> int:
    if destino.exists():
        print(f"{destino.relative_to(BACKEND_DIR)} ya existe; no se reemplaza "
              "(sus claves son las del volumen creado).")
        return 0
    generadas: dict[str, str] = {}
    lineas: list[str] = []
    for linea in PLANTILLA.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            clave, valor = linea.split("=", 1)
            if valor == "__GENERAR__":
                valor = secrets.token_urlsafe(32)
                generadas[clave] = valor
            for nombre, secreto in generadas.items():
                valor = valor.replace("${" + nombre + "}", secreto)
            linea = f"{clave}={valor}"
        lineas.append(linea)
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    try:
        destino.chmod(0o600)
    except OSError:
        pass
    print(f"Creado {destino.relative_to(BACKEND_DIR)} con {len(generadas)} claves aleatorias "
          "(no se muestran; el archivo está en .gitignore).")
    return 0


# ── orquestación ───────────────────────────────────────────────────────────


def ejecutar(*, perfil: str, exigir_tls: bool, espera: float, solo_verificar: bool) -> int:
    os.chdir(BACKEND_DIR)
    total = 6
    entorno = cargar_entorno()

    def paso(numero: int, titulo: str) -> None:
        print(f"[{numero}/{total}] {titulo}", flush=True)

    try:
        paso(1, f"Configuración (perfil {perfil})")
        bases = validar_configuracion(entorno, perfil=perfil, exigir_tls=exigir_tls)
        for base in bases:
            print(f"    {base.servicio}: {base.destino} (rol {base.url.username})")

        paso(2, f"Conexión (hasta {espera:.0f} s)")
        esperar_conexion(bases, segundos=espera)
        print("    las cuatro bases responden")

        paso(3, "Permisos y extensiones")
        revisar_permisos(bases)
        for base in bases:
            for aviso in base.avisos:
                print(f"    aviso {base.servicio}: {aviso}")
        print("    permisos suficientes")

        paso(4, "Estado previo de las migraciones")
        previas = estado_revisiones()
        if mostrar_estado(previas) == 2:
            print("No se migró nada: hay revisiones desconocidas o errores (ver arriba).")
            return 2

        if solo_verificar:
            paso(5, "Migración omitida (verificar)")
        else:
            paso(5, "Migraciones en orden MS1 → MS2 → MS3 → MS4")
            migrar_en_orden(bases)

        paso(6, "Verificación final")
        codigo = verificacion_final(bases)
    except ErrorPaso as exc:
        print(str(exc))
        return exc.codigo

    if codigo == 0:
        print("Base de datos lista: las cuatro bases coinciden con el código.")
    elif solo_verificar and codigo == 1:
        print("Faltan migraciones: ejecutar sin 'verificar' para aplicarlas.")
    return codigo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("accion", nargs="?", default="ejecutar",
                        choices=("ejecutar", "verificar", "configurar"))
    parser.add_argument("--perfil", choices=("despliegue", "local"),
                        default=os.environ.get("SGTM_PERFIL_BD", "despliegue"),
                        help="local admite claves de desarrollo (solo avisa)")
    parser.add_argument("--exigir-tls", action="store_true",
                        default=os.environ.get("SGTM_EXIGIR_TLS", "").lower() == "true",
                        help="exige sslmode=require o verify-* en las cuatro URL")
    parser.add_argument("--espera", type=float,
                        default=float(os.environ.get("SGTM_ESPERA_BD_SEGUNDOS", "60")),
                        help="segundos máximos esperando que las bases respondan")
    args = parser.parse_args(argv)
    if args.accion == "configurar":
        return configurar()
    return ejecutar(perfil=args.perfil, exigir_tls=args.exigir_tls, espera=args.espera,
                    solo_verificar=args.accion == "verificar")


if __name__ == "__main__":
    raise SystemExit(main())
