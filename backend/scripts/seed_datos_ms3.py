"""Datos de prueba de MS3 (Presupuestos, Repuestos y Proveedores).

Carga un catálogo mínimo para probar el servicio: 2 proveedores, 4 repuestos
(uno bajo su umbral para probar alertas), el umbral general de stock con su
historial y un movimiento de ingreso inicial por repuesto. Con --orden-id
también crea el presupuesto de esa orden (versión 1 ENVIADA, sin decisión:
queda lista para probar aprobar/rechazar).

Con --integracion además carga el catálogo de INTEGRACIÓN
(services/ms3_presupuestos/datos_integracion.py): 5 proveedores más, 12
repuestos y sus existencias como movimientos de inventario (ingresos,
consumos, compromisos, liberación y ajuste), cubriendo stock holgado, sin
stock, bajo umbral particular y general, justo en el umbral y unidades
reservadas para una orden. Al final verifica que el stock cuadre con los
movimientos. Con --verificar solo verifica, sin escribir nada.

Es idempotente: se puede correr varias veces sin duplicar nada.

Uso (desde backend/, con las migraciones de MS3 aplicadas y MS3_DATABASE_URL
en .env apuntando a la base que se quiere poblar, local o Neon):
    python scripts/seed_datos_ms3.py
    python scripts/seed_datos_ms3.py --orden-id 1 --admin-id 3 --mecanico-id 2
    python scripts/seed_datos_ms3.py --integracion
    python scripts/seed_datos_ms3.py --integracion --orden-en-reparacion 1 --orden-recibida 2
    python scripts/seed_datos_ms3.py --verificar

Los ids de usuario/orden son REFERENCIAS LÓGICAS a MS1/MS2 (§8): el script no
puede verificarlos, deben existir en esas bases.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ms3_presupuestos import datos_integracion as integ  # noqa: E402
from services.ms3_presupuestos import datos_prueba as datos  # noqa: E402
from services.ms3_presupuestos import semilla_integracion as semilla  # noqa: E402
from services.ms3_presupuestos.db import SessionLocal  # noqa: E402
from services.ms3_presupuestos.models import (  # noqa: E402
    HistorialUmbral,
    ItemPresupuesto,
    MovimientoInventario,
    ParametroInventario,
    Presupuesto,
    Proveedor,
    Repuesto,
    VersionPresupuesto,
)

# El catálogo, el umbral y los ítems de ejemplo vienen de
# services/ms3_presupuestos/datos_prueba.py: la misma fuente que usan las
# fixtures de las pruebas, así la semilla y los tests no se desalinean.
UMBRAL_GENERAL = datos.UMBRAL_GENERAL


def _sembrar_catalogo(db, admin_id: int) -> dict[str, Repuesto]:
    repuestos: dict[str, Repuesto] = {}
    for prov in datos.CATALOGO:
        proveedor = db.scalar(select(Proveedor).where(Proveedor.nombre == prov.nombre))
        if proveedor is None:
            proveedor = Proveedor(nombre=prov.nombre, contacto=prov.contacto,
                                  tipo_distribuidor=prov.tipo_distribuidor)
            db.add(proveedor)
            db.flush()
            print(f"  + Proveedor: {prov.nombre}")
        for item in prov.repuestos:
            nombre, stock, umbral = item.nombre, item.stock, item.umbral_particular
            repuesto = db.scalar(select(Repuesto).where(Repuesto.nombre == nombre))
            if repuesto is None:
                repuesto = Repuesto(proveedor=proveedor, nombre=nombre, stock=stock,
                                    umbral_particular=umbral)
                # Trazabilidad: el alta queda en el historial de proveedores.
                repuesto.registrado_por_id_traza = admin_id
                repuesto.observacion_traza = "Alta del repuesto (semilla)"
                db.add(repuesto)
                db.flush()
                print(f"  + Repuesto: {nombre} (stock {stock})")
                # El stock inicial queda respaldado por un movimiento de ingreso.
                db.add(MovimientoInventario(
                    clave_operacion=f"ingreso-inicial-{repuesto.repuesto_id}",
                    repuesto_id=repuesto.repuesto_id, tipo="ingreso",
                    cantidad=stock, registrado_por_id=admin_id,
                ))
                if umbral is not None:
                    db.add(HistorialUmbral(
                        repuesto_id=repuesto.repuesto_id, valor_anterior=None,
                        valor_nuevo=umbral, administrador_id=admin_id,
                        observacion="Umbral particular inicial",
                    ))
            repuestos[nombre] = repuesto
    return repuestos


def _sembrar_umbral_general(db, admin_id: int) -> None:
    vigente = db.scalar(
        select(ParametroInventario).where(ParametroInventario.vigente_hasta.is_(None))
    )
    if vigente is not None:
        print(f"  ~ Umbral general vigente ya existe ({vigente.umbral_general})")
        return
    db.add(ParametroInventario(umbral_general=UMBRAL_GENERAL, actualizado_por_id=admin_id))
    db.add(HistorialUmbral(repuesto_id=None, valor_anterior=None, valor_nuevo=UMBRAL_GENERAL,
                           administrador_id=admin_id,
                           observacion="Configuracion inicial del umbral general"))
    print(f"  + Umbral general = {UMBRAL_GENERAL}")


def _sembrar_presupuesto(db, orden_id: int, mecanico_id: int,
                         repuestos: dict[str, Repuesto]) -> None:
    if db.scalar(select(Presupuesto).where(Presupuesto.orden_id == orden_id)):
        print(f"  ~ La orden {orden_id} ya tiene presupuesto")
        return
    presupuesto = Presupuesto(orden_id=orden_id)
    version = VersionPresupuesto(numero=1, creado_por_id=mecanico_id)
    version.items += [
        ItemPresupuesto(tipo=i.tipo, descripcion=i.descripcion, cantidad=i.cantidad,
                        precio_unitario=i.precio_unitario,
                        repuesto=repuestos[i.repuesto] if i.repuesto else None)
        for i in datos.ITEMS_PRESUPUESTO_EJEMPLO
    ]
    presupuesto.versiones.append(version)
    db.add(presupuesto)
    db.flush()
    # Enviar = fijar enviado_en. Desde aquí la versión queda congelada (trigger).
    db.refresh(version)
    version.enviado_en = version.creado_en
    db.flush()
    total = sum(i.subtotal for i in version.items)
    print(f"  + Presupuesto orden {orden_id}: version 1 enviada, total ${total:,.0f}")


def _cargar_integracion(admin_id: int, mecanico_id: int, ordenes: dict) -> None:
    print("Sembrando catalogo de integracion en MS3...")
    with SessionLocal() as db:
        r = semilla.cargar_integracion(db, admin_id=admin_id, mecanico_id=mecanico_id,
                                       ordenes=ordenes)
    for nombre in r.proveedores_creados:
        print(f"  + Proveedor: {nombre}")
    for nombre in r.repuestos_creados:
        print(f"  + Repuesto: {nombre}")
    print(f"  Movimientos: {r.movimientos_aplicados} aplicados, "
          f"{r.movimientos_repetidos} ya estaban")


def _verificar(ordenes: dict, *, integracion: bool) -> bool:
    with SessionLocal() as db:
        errores = semilla.verificar_existencias(db)
        avisos = semilla.diferencias_con_semilla(db, ordenes=ordenes) if integracion else []
        vigente = db.scalar(select(ParametroInventario)
                            .where(ParametroInventario.vigente_hasta.is_(None)))
        general = vigente.umbral_general if vigente else None
        print(f"\nExistencias (umbral general vigente: {general}):")
        for r in db.scalars(select(Repuesto).order_by(Repuesto.proveedor_id, Repuesto.nombre)):
            efectivo = r.umbral_particular if r.umbral_particular is not None else general
            alerta = "  <- ALERTA" if efectivo is not None and r.stock < efectivo else ""
            print(f"  {r.proveedor.nombre[:22]:<22} {r.nombre[:34]:<34} stock {r.stock:>3}"
                  f"  umbral {efectivo if efectivo is not None else '-':>2}{alerta}")
    for e in errores:
        print(f"  ERROR: {e}")
    for a in avisos:
        print(f"  AVISO (puede ser uso real de la app): {a}")
    if not errores:
        print("  OK: el stock de todos los repuestos coincide con sus movimientos.")
    return not errores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--admin-id", type=int, default=datos.ADMIN_ID,
                        help="usuario_id (MS1) del administrador (por defecto 3)")
    parser.add_argument("--mecanico-id", type=int, default=datos.MECANICO_ID,
                        help="usuario_id (MS1) del mecanico que arma el presupuesto")
    parser.add_argument("--orden-id", type=int, default=None,
                        help="orden (MS2) para la que se crea un presupuesto de ejemplo")
    parser.add_argument("--integracion", action="store_true",
                        help="carga tambien el catalogo de integracion con sus existencias")
    parser.add_argument("--orden-en-reparacion", type=int,
                        default=integ.ORDENES_POR_DEFECTO["en_reparacion"],
                        help="orden (MS2) que consume repuestos en la semilla (por defecto 1)")
    parser.add_argument("--orden-recibida", type=int,
                        default=integ.ORDENES_POR_DEFECTO["recibida"],
                        help="orden (MS2) con repuestos reservados en la semilla (por defecto 2)")
    parser.add_argument("--verificar", action="store_true",
                        help="solo verifica las existencias, sin escribir nada")
    args = parser.parse_args()
    ordenes = {"en_reparacion": args.orden_en_reparacion, "recibida": args.orden_recibida}

    if args.verificar:
        sys.exit(0 if _verificar(ordenes, integracion=True) else 1)

    print("Sembrando datos de prueba en MS3...")
    with SessionLocal() as db:
        repuestos = _sembrar_catalogo(db, args.admin_id)
        _sembrar_umbral_general(db, args.admin_id)
        if args.orden_id is not None:
            _sembrar_presupuesto(db, args.orden_id, args.mecanico_id, repuestos)
        db.commit()
    if args.integracion:
        _cargar_integracion(args.admin_id, args.mecanico_id, ordenes)
    ok = _verificar(ordenes, integracion=args.integracion)
    print("Seed de MS3 completado." if ok else "Seed de MS3 terminado CON ERRORES.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
