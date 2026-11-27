"""Verificación de secretos y configuración por ambiente (Semana 11).

Revisa dos cosas sin imprimir nunca un valor secreto:

1. --repo: que el repositorio (público) no tenga archivos .env versionados ni
   credenciales reales en los archivos que sigue Git, y que .gitignore cubra
   los archivos de entorno que usan los scripts.
2. --ambiente local|kubero: que un conjunto de variables (el .env local o las
   variables copiadas del panel de Kubero) sea coherente con lo que exigen los
   servicios: JWT igual en MS1-MS4, secretos de servicio emparejados, nada de
   valores de plantilla, y en Kubero nada de localhost, CORS solo HTTPS, etc.

Solo usa la biblioteca estándar, así corre sin instalar el backend.

Uso (desde backend/):
    python scripts/verificar_config_ambiente.py --repo
    python scripts/verificar_config_ambiente.py --ambiente local --archivo .env
    python scripts/verificar_config_ambiente.py --ambiente kubero \\
        --archivo gateway=.env.gateway.kubero.local \\
        --archivo ms1=.env.ms1.kubero.local ...

Para Kubero, copiar las variables de cada app del panel a un archivo
`.env.<app>.kubero.local` (lo ignora .gitignore por `.env.*.local`) y borrarlo
al terminar. Sale con 1 si hay alguna FALLA.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

RAIZ_BACKEND = Path(__file__).resolve().parents[1]

SERVICIOS = ("MS1", "MS2", "MS3", "MS4")
LARGO_MINIMO = 32  # el mismo min_length que piden los config.py

# Pares de secretos que deben ser idénticos en emisor y receptor (docs/03 §1).
PARES_SECRETOS = (
    ("MS1_EVENT_SHARED_SECRET", "MS2_EVENT_SHARED_SECRET"),
    ("MS1_MS3_EVENT_SHARED_SECRET", "MS3_EVENT_SHARED_SECRET"),
    ("MS1_MS2_NOTIFICATION_SECRET", "MS2_NOTIFICATION_LOOKUP_SECRET"),
)

# Restos de las plantillas .env.example o valores por defecto del código.
MARCAS_PLANTILLA = ("reemplaza", "cambia-esta", "<secreto>", "changeme", "<pruebas_pg_clave>")
CLAVES_DEBILES_BD = {"taller", "postgres", "password", "admin", "123456"}
HOSTS_LOCALES = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

# Variables que la Gateway no debe tener: solo enruta (docs/03 §2).
PROHIBIDAS_EN_GATEWAY = re.compile(r"(JWT_SECRET|DATABASE_URL|SHARED_SECRET|S3_SECRET|NOTIFICATION.*SECRET)")

# Patrones de credenciales reales para la revisión del repositorio.
PATRONES_REPO = {
    "token de GitHub": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "llave AWS": re.compile(r"AKIA[0-9A-Z]{16}"),
    "llave privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "JWT emitido": re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{20,}"),
    "clave de base administrada (npg_)": re.compile(r"npg_[A-Za-z0-9]{10,}"),
    "DSN con clave": re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^:/\s@]+:([^@\s'\"]+)@"),
}
# Código legado que no se despliega (docs/08): un hallazgo ahí es aviso, no falla.
RUTAS_LEGADO = ("presupuestos-service/", "auth-service/", "backend/_legacy_monolito_")

# Claves de DSN que son de ejemplo o vienen de una variable, no reales.
CLAVE_DSN_PERMITIDA = re.compile(
    r"^(\$\{?\w+\}?|\{\w+\}|<\w+>|taller|postgres|password|PASSWORD|secreto|clave|CLAVE|x+)$"
)


@dataclass
class Reporte:
    lineas: list[tuple[str, str]] = field(default_factory=list)

    def ok(self, msg: str) -> None:
        self.lineas.append(("OK", msg))

    def aviso(self, msg: str) -> None:
        self.lineas.append(("AVISO", msg))

    def falla(self, msg: str) -> None:
        self.lineas.append(("FALLA", msg))

    @property
    def fallas(self) -> int:
        return sum(1 for nivel, _ in self.lineas if nivel == "FALLA")

    def imprimir(self) -> None:
        for nivel, msg in self.lineas:
            print(f"  [{nivel:^5}] {msg}")
        avisos = sum(1 for n, _ in self.lineas if n == "AVISO")
        print(f"\nResultado: {self.fallas} falla(s), {avisos} aviso(s).")


# ---------------------------------------------------------------------------
# Lectura de variables
# ---------------------------------------------------------------------------

def leer_env(ruta: Path) -> dict[str, str]:
    """Lee KEY=VALOR (como python-dotenv, sin expandir variables)."""
    valores: dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.removeprefix("export ").strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "'\"":
            valor = valor[1:-1]
        valores[clave] = valor
    return valores


def _es_plantilla(valor: str) -> bool:
    bajo = valor.lower()
    return any(marca in bajo for marca in MARCAS_PLANTILLA)


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


# ---------------------------------------------------------------------------
# Verificación del ambiente
# ---------------------------------------------------------------------------

def verificar_jwt(env: dict[str, str], rep: Reporte, kubero: bool) -> None:
    claves = {s: env.get(f"{s}_JWT_SECRET_KEY", "") for s in SERVICIOS}
    faltan = [s for s, v in claves.items() if not v]
    if faltan:
        rep.falla(f"JWT: falta {', '.join(f'{s}_JWT_SECRET_KEY' for s in faltan)}")
    cortos = [s for s, v in claves.items() if v and len(v) < LARGO_MINIMO]
    if cortos:
        rep.falla(f"JWT: menos de {LARGO_MINIMO} caracteres en {', '.join(cortos)} (el servicio no arranca)")
    plantilla = [s for s, v in claves.items() if v and _es_plantilla(v)]
    if plantilla:
        (rep.falla if kubero else rep.aviso)(f"JWT: valor de plantilla en {', '.join(plantilla)}")
    presentes = {v for v in claves.values() if v}
    if len(presentes) > 1 and plantilla and not kubero:
        rep.aviso("JWT: los valores de plantilla difieren; en un .env real deben ser iguales")
    elif len(presentes) > 1:
        rep.falla("JWT: MS1-MS4 no tienen el mismo secreto (HS256 rechazaría los tokens)")
    elif presentes and not (faltan or cortos):
        rep.ok("JWT: presente, largo suficiente e igual en MS1-MS4")
    for s in SERVICIOS:
        algoritmo = env.get(f"{s}_JWT_ALGORITHM", "HS256")
        if algoritmo != "HS256":
            rep.falla(f"JWT: {s}_JWT_ALGORITHM={algoritmo}; los servicios solo aceptan HS256")


def verificar_pares(env: dict[str, str], rep: Reporte, kubero: bool) -> None:
    jwt = env.get("MS1_JWT_SECRET_KEY", "")
    for a, b in PARES_SECRETOS:
        va, vb = env.get(a, ""), env.get(b, "")
        if not va and not vb:
            rep.aviso(f"{a} / {b}: sin configurar (esa integración queda apagada)")
            continue
        if not va or not vb:
            rep.falla(f"{a} / {b}: solo uno de los dos está definido")
            continue
        problemas = []
        if va != vb:
            problemas.append("no coinciden")
        if min(len(va), len(vb)) < LARGO_MINIMO:
            problemas.append(f"menos de {LARGO_MINIMO} caracteres")
        if jwt and jwt in (va, vb):
            problemas.append("reutilizan el secreto JWT")
        if _es_plantilla(va) or _es_plantilla(vb):
            problemas.append("valor de plantilla")
        if not problemas:
            rep.ok(f"{a} / {b}: coinciden y son distintos al JWT")
        elif "valor de plantilla" in problemas and not kubero and set(problemas) <= {"valor de plantilla", "no coinciden"}:
            rep.aviso(f"{a} / {b}: valor de plantilla (aceptable solo en local)")
        else:
            rep.falla(f"{a} / {b}: {', '.join(problemas)}")


def verificar_workers(env: dict[str, str], rep: Reporte) -> None:
    for servicio in ("MS2", "MS3"):
        activo = env.get(f"{servicio}_EVENT_WORKER_ENABLED", "").lower() == "true"
        secreto = env.get(f"{servicio}_EVENT_SHARED_SECRET", "")
        if activo and not secreto:
            rep.falla(f"{servicio}: worker de eventos activo sin {servicio}_EVENT_SHARED_SECRET")
        elif secreto and not activo:
            rep.aviso(f"{servicio}: hay secreto de eventos pero el worker está apagado (no salen avisos)")
    if env.get("MS1_NOTIFICATION_WORKER_ENABLED", "").lower() == "false":
        rep.aviso("MS1: worker de correo apagado (SMTP pendiente, docs/08)")


def verificar_bases(env: dict[str, str], rep: Reporte, kubero: bool) -> None:
    destinos = {}
    for s in SERVICIOS:
        url = env.get(f"{s}_DATABASE_URL", "")
        if not url:
            rep.falla(f"{s}_DATABASE_URL: no definida")
            continue
        partes = urlsplit(url)
        if partes.scheme != "postgresql+psycopg":
            rep.falla(f"{s}_DATABASE_URL: el esquema debe ser postgresql+psycopg")
        clave = partes.password or ""
        if kubero and (clave.lower() in CLAVES_DEBILES_BD or len(clave) < 12 or _es_plantilla(clave)):
            rep.falla(f"{s}_DATABASE_URL: clave de base débil o de ejemplo")
        if kubero and (partes.hostname or "") in HOSTS_LOCALES:
            rep.falla(f"{s}_DATABASE_URL: apunta a localhost (dentro del pod es el propio pod)")
        destinos[s] = (partes.hostname, partes.port, partes.path)
    repetidos = {d for d in destinos.values() if list(destinos.values()).count(d) > 1}
    if repetidos:
        rep.falla("DATABASE_URL: dos servicios apuntan a la misma base (§8, una base por servicio)")
    elif len(destinos) == len(SERVICIOS):
        rep.ok("DATABASE_URL: cuatro bases distintas, una por microservicio")


def verificar_urls_internas(env: dict[str, str], rep: Reporte) -> None:
    locales = sorted(
        k for k, v in env.items()
        if (k.endswith("_URL") or k.endswith("_ENDPOINT") or k == "GATEWAY_UPSTREAM")
        and not k.endswith("DATABASE_URL") and _host(v) in HOSTS_LOCALES
    )
    if locales:
        rep.falla(f"URLs con localhost en Kubero: {', '.join(locales)}")
    else:
        rep.ok("URLs entre servicios: ninguna apunta a localhost")


def verificar_cors(env: dict[str, str], rep: Reporte, kubero: bool) -> None:
    if "GATEWAY_CORS_ORIGINS" not in env:
        return
    origenes = [o.strip() for o in re.split(r"[,\s]+", env["GATEWAY_CORS_ORIGINS"].strip("[]\"' ")) if o.strip().strip("\"'")]
    origenes = [o.strip("\"'") for o in origenes]
    problemas = []
    if "*" in origenes:
        problemas.append("usa '*'")
    if kubero:
        if any(_host(o) in HOSTS_LOCALES for o in origenes):
            problemas.append("incluye localhost")
        if any(not o.startswith("https://") for o in origenes if o != "*"):
            problemas.append("hay orígenes sin HTTPS")
        if env.get("GATEWAY_CORS_ORIGIN_REGEX", "").strip():
            problemas.append("GATEWAY_CORS_ORIGIN_REGEX no está vacío (autoriza previews)")
    if problemas:
        rep.falla(f"CORS de la Gateway: {', '.join(problemas)}")
    else:
        rep.ok(f"CORS de la Gateway: {len(origenes)} origen(es) explícito(s)")


def verificar_ms4(env: dict[str, str], rep: Reporte, kubero: bool) -> None:
    secreto = env.get("MS4_S3_SECRET_KEY", "")
    if kubero:
        if not secreto or secreto == "cambia-esta-clave-ms4" or _es_plantilla(secreto) or len(secreto) < 16:
            rep.falla("MS4_S3_SECRET_KEY: vacía, corta o igual al valor por defecto del código")
        else:
            rep.ok("MS4_S3_SECRET_KEY: definida y distinta al valor por defecto")
        publico = env.get("MS4_S3_PUBLIC_ENDPOINT", "")
        interno = env.get("MS4_S3_ENDPOINT", "")
        if not publico.startswith("https://"):
            rep.falla("MS4_S3_PUBLIC_ENDPOINT: debe ser el dominio público con HTTPS (URLs firmadas)")
        elif interno and _host(interno) == _host(publico):
            rep.aviso("MS4: S3_ENDPOINT y S3_PUBLIC_ENDPOINT son el mismo host (MS4 sale a Internet)")
        else:
            rep.ok("MS4: endpoint S3 interno y público separados, público con HTTPS")
    elif secreto == "cambia-esta-clave-ms4" or not secreto:
        rep.aviso("MS4_S3_SECRET_KEY: usa el valor por defecto (solo válido en local)")


def verificar_gateway_sin_secretos(env_gateway: dict[str, str], rep: Reporte) -> None:
    sobran = sorted(k for k in env_gateway if PROHIBIDAS_EN_GATEWAY.search(k))
    if sobran:
        rep.falla(f"gateway: tiene variables que no necesita ({', '.join(sobran)})")
    else:
        rep.ok("gateway: no recibe JWT, DSN ni secretos de servicio")


def verificar_ambiente(env: dict[str, str], ambiente: str, env_gateway: dict[str, str] | None = None) -> Reporte:
    kubero = ambiente == "kubero"
    rep = Reporte()
    verificar_jwt(env, rep, kubero)
    verificar_pares(env, rep, kubero)
    verificar_workers(env, rep)
    verificar_bases(env, rep, kubero)
    verificar_cors(env, rep, kubero)
    verificar_ms4(env, rep, kubero)
    if kubero:
        verificar_urls_internas(env, rep)
        if env_gateway is not None:
            verificar_gateway_sin_secretos(env_gateway, rep)
    return rep


# ---------------------------------------------------------------------------
# Verificación del repositorio
# ---------------------------------------------------------------------------

def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=RAIZ_BACKEND.parent, capture_output=True, text=True, check=True
    ).stdout


def buscar_credenciales(texto: str) -> list[str]:
    """Nombres de los patrones de credencial real encontrados en un texto."""
    hallados = []
    for nombre, patron in PATRONES_REPO.items():
        for coincidencia in patron.finditer(texto):
            if nombre == "DSN con clave" and CLAVE_DSN_PERMITIDA.match(coincidencia.group(1)):
                continue
            if nombre == "DSN con clave" and coincidencia.group(1).startswith(("${", "{")):
                continue
            hallados.append(nombre)
            break
    return hallados


def verificar_repo() -> Reporte:
    rep = Reporte()
    archivos = _git("ls-files").splitlines()

    env_versionados = [
        a for a in archivos
        if re.search(r"(^|/)\.env(\.|$)", a) and not a.endswith(".example")
    ]
    if env_versionados:
        rep.falla(f"Archivos de entorno versionados: {', '.join(env_versionados)}")
    else:
        rep.ok("Ningún .env versionado (solo plantillas .example)")

    con_hallazgos = []
    for ruta in archivos:
        destino = RAIZ_BACKEND.parent / ruta
        if destino.suffix in {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".mp4", ".ico", ".drawio"}:
            continue
        if ruta.endswith(("package-lock.json", ".lock")) or ruta.startswith("backend/tests/"):
            continue
        try:
            texto = destino.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hallados = buscar_credenciales(texto)
        if hallados:
            con_hallazgos.append(f"{ruta} ({', '.join(hallados)})")
    if con_hallazgos:
        for linea in con_hallazgos:
            if linea.startswith(RUTAS_LEGADO):
                rep.aviso(f"Clave de desarrollo en código legado sin desplegar: {linea}")
            else:
                rep.falla(f"Posible credencial en {linea}")
    else:
        rep.ok(f"Sin credenciales reales en {len(archivos)} archivos versionados")

    deben_ignorarse = (
        "backend/.env", "backend/.env.pruebas", "backend/despliegue/.env.despliegue",
        "backend/.env.gateway.kubero.local", "frontend/.env",
    )
    no_ignorados = []
    for ruta in deben_ignorarse:
        resultado = subprocess.run(
            ["git", "check-ignore", "-q", ruta], cwd=RAIZ_BACKEND.parent
        )
        if resultado.returncode != 0:
            no_ignorados.append(ruta)
    if no_ignorados:
        rep.falla(f".gitignore no cubre: {', '.join(no_ignorados)}")
    else:
        rep.ok(".gitignore cubre .env, .env.pruebas, .env.despliegue y .env.*.local")
    return rep


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", action="store_true", help="revisar el repositorio")
    parser.add_argument("--ambiente", choices=("local", "kubero"))
    parser.add_argument(
        "--archivo", action="append", default=[],
        help="archivo de variables; con prefijo app= (p. ej. gateway=ruta) se revisa por app",
    )
    args = parser.parse_args(argv)
    if not args.repo and not args.ambiente:
        parser.error("indica --repo, --ambiente o ambos")

    fallas = 0
    if args.repo:
        print("==> Repositorio")
        rep = verificar_repo()
        rep.imprimir()
        fallas += rep.fallas

    if args.ambiente:
        if not args.archivo:
            parser.error("--ambiente necesita al menos un --archivo")
        env: dict[str, str] = {}
        env_gateway = None
        for item in args.archivo:
            app, _, ruta = item.rpartition("=") if "=" in item else ("", "", item)
            valores = leer_env(Path(ruta))
            if app == "gateway":
                env_gateway = valores
            env.update(valores)
        print(f"\n==> Ambiente {args.ambiente} ({len(env)} variables, valores no se muestran)")
        rep = verificar_ambiente(env, args.ambiente, env_gateway)
        rep.imprimir()
        fallas += rep.fallas

    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
