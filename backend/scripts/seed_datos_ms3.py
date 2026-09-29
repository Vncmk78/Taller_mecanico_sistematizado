"""Datos de prueba de MS3 (Presupuestos, Repuestos y Proveedores).

Carga un catálogo mínimo para probar el servicio: 2 proveedores, 4 repuestos
(uno bajo su umbral para probar alertas), el umbral general de stock con su
historial y un movimiento de ingreso inicial por repuesto. Con --orden-id
también crea el presupuesto de esa orden (versión 1 ENVIADA, sin decisión:
queda lista para probar aprobar/rechazar).

Es idempotente: se puede correr varias veces sin duplicar nada.

Uso (desde backend/, con las migraciones de MS3 aplicadas y MS3_DATABASE_URL
en .env apuntando a la base que se quiere poblar, local o Neon):
    python scripts/seed_datos_ms3.py
    python scripts/seed_datos_ms3.py --orden-id 1 --admin-id 3 --mecanico-id 2

Los ids de usuario/orden son REFERENCIAS LÓGICAS a MS1/MS2 (§8): el script no
puede verificarlos, deben existir en esas bases.
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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

UMBRAL_GENERAL = 5

# proveedor -> [(repuesto, stock, umbral_particular)]
CATALOGO = {
    ("Frenos del Sur", "contacto@frenosdelsur.cl / +56 9 8765 4321"): [
        ("Pastillas de freno delanteras", 10, 4),
        ("Disco de freno delantero", 2, 3),  # bajo su umbral: dispara alerta
    ],
    ("Repuestos Temuco", "ventas@repuestostemuco.cl / +56 45 221 0000"): [
        ("Filtro de aceite", 15, None),
        ("Aceite 10W-40 (litro)", 24, None),
    ],
}


def _sembrar_catalogo(db, admin_id: int) -> dict[str, Repuesto]:
    repuestos: dict[str, Repuesto] = {}
    for (nombre_prov, contacto), items in CATALOGO.items():
        proveedor = db.scalar(select(Proveedor).where(Proveedor.nombre == nombre_prov))
        if proveedor is None:
            proveedor = Proveedor(nombre=nombre_prov, contacto=contacto)
            db.add(proveedor)
            db.flush()
            print(f"  + Proveedor: {nombre_prov}")
        for nombre, stock, umbral in items:
            repuesto = db.scalar(select(Repuesto).where(Repuesto.nombre == nombre))
            if repuesto is None:
                repuesto = Repuesto(proveedor=proveedor, nombre=nombre, stock=stock,
                                    umbral_particular=umbral)
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
        ItemPresupuesto(tipo="repuesto", repuesto=repuestos["Pastillas de freno delanteras"],
                        descripcion="Juego de pastillas de freno delanteras",
                        cantidad=Decimal("1"), precio_unitario=Decimal("38990")),
        ItemPresupuesto(tipo="mano_de_obra", descripcion="Cambio de pastillas y revision de frenos",
                        cantidad=Decimal("1.5"), precio_unitario=Decimal("20000")),
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--admin-id", type=int, default=3,
                        help="usuario_id (MS1) del administrador (por defecto 3)")
    parser.add_argument("--mecanico-id", type=int, default=2,
                        help="usuario_id (MS1) del mecanico que arma el presupuesto")
    parser.add_argument("--orden-id", type=int, default=None,
                        help="orden (MS2) para la que se crea un presupuesto de ejemplo")
    args = parser.parse_args()

    print("Sembrando datos de prueba en MS3...")
    with SessionLocal() as db:
        repuestos = _sembrar_catalogo(db, args.admin_id)
        _sembrar_umbral_general(db, args.admin_id)
        if args.orden_id is not None:
            _sembrar_presupuesto(db, args.orden_id, args.mecanico_id, repuestos)
        db.commit()
    print("Seed de MS3 completado.")


if __name__ == "__main__":
    main()
