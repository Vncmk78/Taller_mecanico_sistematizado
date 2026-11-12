"""Carga, verifica, limpia y reinicia los datos controlados de demostración.

Los datos son SIEMPRE los mismos (reproducibles) y salen de los seeds que ya
usa el equipo, en este orden:
  1. seed_usuarios_prueba.py   7 cuentas (cada rol y combinación) + perfiles Cliente en MS2.
  2. seed_datos_ms3.py         catálogo base de MS3 (proveedores, repuestos, stock, umbral).
  3. sembrar_demo_pruebas.py   (solo con --gateway) escenarios DEMO01..DEMO09 creados
                               por la API, con las reglas reales de la aplicación.

Acciones:
  estado                         marca de cada base y conteos principales
  cargar   [--gateway URL]       carga los datos (idempotente)
  verificar [--escenarios]       comprueba que los datos controlados están completos
  limpiar  --confirmar LIMPIAR-DEMO
                                 vacía el esquema de las 4 bases y vuelve a migrar a
                                 heads: quedan solo los datos de referencia de las
                                 migraciones (roles, estados, etc.)
  reiniciar --confirmar LIMPIAR-DEMO [--gateway URL]
                                 limpiar + cargar (+ verificar)

Protección: ninguna acción que escribe se ejecuta si alguna de las cuatro bases
no tiene una marca de ambiente de demostración en su comentario
(COMMENT ON DATABASE). Las bases de producción no la tienen, así que nunca se
cargan cuentas con claves conocidas ni se borran datos reales. La marca la pone
despliegue/initdb (SGTM_BD_MARCA=sgtm-despliegue-demo) o el ambiente de pruebas.

Lee la configuración igual que inicializar_bd.py (backend/.env o SGTM_ENV_FILE).
Códigos de salida: 0 correcto, 1 datos incompletos, 2 error o protección activa.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts import inicializar_bd as ini  # noqa: E402

CONFIRMACION = "LIMPIAR-DEMO"
MARCAS_DEMO = {"sgtm-despliegue-demo", "sgtm-ambiente-pruebas", "sgtm-ambiente-demo-final"}
ORDEN_LIMPIEZA = ("MS4", "MS3", "MS2", "MS1")  # inverso al de migración

# Conteos que se muestran en `estado` (tabla, descripción) por servicio.
CONTEOS = {
    "MS1": (("usuario", "usuarios"), ("usuario_rol", "roles asignados"), ("notificacion", "notificaciones")),
    "MS2": (("cliente", "clientes"), ("vehiculo", "vehículos"), ("orden_trabajo", "órdenes")),
    "MS3": (("proveedor", "proveedores"), ("repuesto", "repuestos"), ("presupuesto", "presupuestos")),
    "MS4": (("evidencia", "evidencias"),),
}


class ErrorDemo(Exception):
    pass


# ── conexión y protección ──────────────────────────────────────────────────


def preparar(perfil: str) -> list[ini.Base]:
    os.chdir(BACKEND_DIR)
    entorno = ini.cargar_entorno()
    try:
        bases = ini.validar_configuracion(entorno, perfil=perfil, exigir_tls=False)
        ini.esperar_conexion(bases, segundos=float(entorno.get("SGTM_ESPERA_BD_SEGUNDOS", "20")))
    except ini.ErrorPaso as exc:
        raise ErrorDemo(str(exc)) from exc
    return bases


def marca(base: ini.Base) -> str | None:
    engine = ini._engine(base)
    try:
        with engine.connect() as conexion:
            return conexion.execute(text(
                "SELECT shobj_description(oid, 'pg_database') FROM pg_database"
                " WHERE datname = current_database()"
            )).scalar()
    finally:
        engine.dispose()


def exigir_marcas(bases: list[ini.Base]) -> None:
    sin_marca = [f"{b.servicio} ({b.destino}: {marca(b) or 'sin marca'})"
                 for b in bases if marca(b) not in MARCAS_DEMO]
    if sin_marca:
        raise ErrorDemo(
            "Protección activa: estas bases no están marcadas como ambiente de demostración:\n  - "
            + "\n  - ".join(sin_marca)
            + "\nNo se escribió nada. Ver docs/datos-demostracion.md (marcar una base)."
        )


def exigir_migradas() -> None:
    resultados = ini.estado_revisiones()
    if ini.mostrar_estado(resultados) != 0:
        raise ErrorDemo("Las bases no están en heads: ejecutar antes scripts/inicializar_bd.py.")


# ── estado ─────────────────────────────────────────────────────────────────


def _contar(conexion, tabla: str) -> str:
    existe = conexion.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}).scalar()
    if not existe:
        return "-"
    return str(conexion.exec_driver_sql(f'SELECT count(*) FROM public."{tabla}"').scalar())


def estado(bases: list[ini.Base]) -> int:
    for base in bases:
        engine = ini._engine(base)
        try:
            with engine.connect() as conexion:
                partes = [f"{desc} {_contar(conexion, tabla)}" for tabla, desc in CONTEOS[base.servicio]]
        finally:
            engine.dispose()
        print(f"{base.servicio} {base.destino} [{marca(base) or 'sin marca'}]: " + ", ".join(partes))
    return 0


# ── cargar ─────────────────────────────────────────────────────────────────


def _correr(*argumentos: str) -> None:
    print(f"$ python {' '.join(argumentos)}", flush=True)
    resultado = subprocess.run([sys.executable, *argumentos], cwd=BACKEND_DIR, env=dict(os.environ), check=False)
    if resultado.returncode:
        raise ErrorDemo(f"{argumentos[0]} terminó con código {resultado.returncode}")


def _ids(correos: tuple[str, ...]) -> list[int]:
    from sqlalchemy import select

    from services.ms1_auth.db import SessionLocal
    from services.ms1_auth.models.usuario import Usuario

    with SessionLocal() as db:
        ids = [db.scalar(select(Usuario.usuario_id).where(Usuario.correo == c)) for c in correos]
    if None in ids:
        raise ErrorDemo("No se encontraron las cuentas de Administrador y Mecánico de prueba")
    return ids


def cargar(bases: list[ini.Base], gateway: str | None) -> None:
    exigir_marcas(bases)
    exigir_migradas()
    _correr("scripts/seed_usuarios_prueba.py")
    admin_id, mecanico_id = _ids(("administrador@pruebas.cl", "mecanico@pruebas.cl"))
    _correr("scripts/seed_datos_ms3.py", "--admin-id", str(admin_id), "--mecanico-id", str(mecanico_id))
    if gateway:
        _correr("scripts/sembrar_demo_pruebas.py", "--gateway", gateway)
    else:
        print("Escenarios DEMO01..09 omitidos: requieren los servicios levantados (--gateway URL).")


# ── verificar ──────────────────────────────────────────────────────────────


def esperado() -> dict:
    from scripts.seed_usuarios_prueba import USUARIOS
    from scripts.sembrar_demo_pruebas import ESCENARIOS
    from services.ms3_presupuestos import datos_prueba
    from shared.auth import NombreRol

    return {
        "correos": [u["correo"] for u in USUARIOS],
        "clientes": [u["correo"] for u in USUARIOS if NombreRol.CLIENTE in u["roles"]],
        "proveedores": [p.nombre for p in datos_prueba.CATALOGO],
        "repuestos": [r.nombre for p in datos_prueba.CATALOGO for r in p.repuestos],
        "escenarios": {patente: (None if final is None else int(str(final)[0]))
                       for patente, *_, final in ESCENARIOS},
    }


def verificar(bases: list[ini.Base], *, escenarios: bool) -> int:
    datos = esperado()
    por_servicio = {b.servicio: b for b in bases}
    fallos: list[str] = []

    def consulta(servicio: str, sql: str, **params):
        engine = ini._engine(por_servicio[servicio])
        try:
            with engine.connect() as conexion:
                return conexion.execute(text(sql), params).all()
        finally:
            engine.dispose()

    usuarios = {f.correo: f.activos for f in consulta(
        "MS1",
        "SELECT u.correo, count(ur.rol_id) AS activos FROM usuario u"
        " LEFT JOIN usuario_rol ur ON ur.usuario_id = u.usuario_id"
        " WHERE u.correo = ANY(:c) GROUP BY u.correo", c=datos["correos"])}
    faltan = [c for c in datos["correos"] if c not in usuarios]
    if faltan:
        fallos.append(f"MS1: faltan cuentas {', '.join(faltan)}")
    sin_rol = [c for c, n in usuarios.items() if n == 0]
    if sin_rol:
        fallos.append(f"MS1: cuentas sin rol {', '.join(sin_rol)}")
    print(f"MS1: {len(usuarios)}/{len(datos['correos'])} cuentas de prueba")

    clientes = consulta("MS2", "SELECT count(*) FROM cliente")[0][0]
    if clientes < len(datos["clientes"]):
        fallos.append(f"MS2: {clientes} perfiles Cliente, se esperaban {len(datos['clientes'])}")
    print(f"MS2: {clientes} perfiles Cliente (esperados {len(datos['clientes'])})")

    proveedores = {f[0] for f in consulta("MS3", "SELECT nombre FROM proveedor WHERE nombre = ANY(:n)",
                                           n=datos["proveedores"])}
    repuestos = {f[0] for f in consulta("MS3", "SELECT nombre FROM repuesto WHERE nombre = ANY(:n)",
                                         n=datos["repuestos"])}
    for tipo, encontrados in (("proveedores", proveedores), ("repuestos", repuestos)):
        faltantes = sorted(set(datos[tipo]) - encontrados)
        if faltantes:
            fallos.append(f"MS3: faltan {tipo} {', '.join(faltantes)}")
    print(f"MS3: {len(proveedores)}/{len(datos['proveedores'])} proveedores, "
          f"{len(repuestos)}/{len(datos['repuestos'])} repuestos")

    if escenarios:
        filas = consulta(
            "MS2",
            "SELECT v.patente, (SELECT o.estado_codigo FROM orden_trabajo o"
            "  WHERE o.vehiculo_id = v.vehiculo_id ORDER BY o.orden_id DESC LIMIT 1) AS estado"
            " FROM vehiculo v WHERE v.patente = ANY(:p)", p=list(datos["escenarios"]))
        reales = {f.patente: f.estado for f in filas}
        for patente, estado_esperado in datos["escenarios"].items():
            if patente not in reales:
                fallos.append(f"MS2: falta el vehículo {patente}")
            elif reales[patente] != estado_esperado:
                fallos.append(f"MS2: {patente} en estado {reales[patente]}, se esperaba {estado_esperado}")
        print(f"MS2: {len(reales)}/{len(datos['escenarios'])} escenarios DEMO")

    for fallo in fallos:
        print(f"  - {fallo}")
    print("Datos controlados completos." if not fallos else "Datos controlados INCOMPLETOS.")
    return 1 if fallos else 0


# ── limpiar ────────────────────────────────────────────────────────────────

# Objetos de la aplicación en public, excluyendo los que pertenecen a extensiones
# (pg_trgm y unaccent se conservan; la migración usa CREATE EXTENSION IF NOT EXISTS).
SQL_OBJETOS = """
SELECT 'TABLE' AS tipo, format('%I.%I', n.nspname, c.relname) AS nombre
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')
UNION ALL
SELECT 'VIEW', format('%I.%I', n.nspname, c.relname)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('v', 'm')
   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')
UNION ALL
SELECT 'SEQUENCE', format('%I.%I', n.nspname, c.relname)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind = 'S'
   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype IN ('e', 'a', 'i'))
UNION ALL
SELECT 'TYPE', format('%I.%I', n.nspname, t.typname)
  FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
 WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd')
   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = t.oid AND d.deptype = 'e')
UNION ALL
SELECT 'FUNCTION', p.oid::regprocedure::text
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'public'
   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
"""


def vaciar_esquema(base: ini.Base) -> int:
    engine = ini._engine(base)
    try:
        with engine.begin() as conexion:
            conexion.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
            conexion.exec_driver_sql("SET LOCAL statement_timeout = '60s'")
            if conexion.execute(text(
                "SELECT shobj_description(oid, 'pg_database') FROM pg_database"
                " WHERE datname = current_database()")).scalar() not in MARCAS_DEMO:
                raise ErrorDemo(f"{base.servicio}: la base perdió la marca de demostración; no se borra")
            objetos = conexion.execute(text(SQL_OBJETOS)).all()
            for tipo in ("VIEW", "TABLE", "SEQUENCE", "FUNCTION", "TYPE"):
                nombres = [o.nombre for o in objetos if o.tipo == tipo]
                if nombres:
                    conexion.exec_driver_sql(f"DROP {tipo} IF EXISTS {', '.join(nombres)} CASCADE")
            restantes = conexion.execute(text(
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")).scalar()
            if restantes:
                raise ErrorDemo(f"{base.servicio}: quedaron {restantes} tablas de otro dueño; se revierte")
            return len(objetos)
    finally:
        engine.dispose()


def limpiar(bases: list[ini.Base], confirmacion: str | None) -> None:
    if confirmacion != CONFIRMACION:
        raise ErrorDemo(f"Para limpiar hay que pasar --confirmar {CONFIRMACION}. No se borró nada.")
    exigir_marcas(bases)
    por_servicio = {b.servicio: b for b in bases}
    for servicio in ORDEN_LIMPIEZA:
        cantidad = vaciar_esquema(por_servicio[servicio])
        print(f"{servicio}: {cantidad} objetos eliminados", flush=True)
    print("Recreando el esquema con las migraciones (MS1 → MS4)...", flush=True)
    try:
        ini.migrar_en_orden(bases)
    except ini.ErrorPaso as exc:
        raise ErrorDemo(str(exc)) from exc
    if ini.verificacion_final(bases) != 0:
        raise ErrorDemo("El esquema recreado no coincide con el código")
    print("Bases limpias: solo esquema y datos de referencia de las migraciones.")
    print("Los archivos de evidencias en MinIO/S3 quedan huérfanos: "
          "python scripts/limpiar_huerfanos_ms4.py --antiguedad-minutos 1 --eliminar")


# ── main ───────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("accion", choices=("estado", "cargar", "verificar", "limpiar", "reiniciar"))
    parser.add_argument("--gateway", help="URL de la Gateway para crear los escenarios DEMO por la API")
    parser.add_argument("--escenarios", action="store_true", help="verificar también DEMO01..DEMO09")
    parser.add_argument("--confirmar", help=f"debe ser {CONFIRMACION} para limpiar o reiniciar")
    parser.add_argument("--perfil", choices=("despliegue", "local"),
                        default=os.environ.get("SGTM_PERFIL_BD", "despliegue"))
    args = parser.parse_args(argv)
    try:
        if args.accion in ("limpiar", "reiniciar") and args.confirmar != CONFIRMACION:
            raise ErrorDemo(f"Para {args.accion} hay que pasar --confirmar {CONFIRMACION}. No se borró nada.")
        bases = preparar(args.perfil)
        if args.accion == "estado":
            return estado(bases)
        if args.accion == "verificar":
            return verificar(bases, escenarios=args.escenarios)
        if args.accion in ("limpiar", "reiniciar"):
            limpiar(bases, args.confirmar)
        if args.accion in ("cargar", "reiniciar"):
            cargar(bases, args.gateway)
            codigo = verificar(bases, escenarios=bool(args.gateway))
            estado(bases)
            return codigo
        return estado(bases)
    except ErrorDemo as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
