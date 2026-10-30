"""Carga y verificación de los datos semilla de integración de MS3.

`cargar_integracion` registra el catálogo de `datos_integracion.py` usando los
MISMOS casos de uso que la API (services/catalogo.py y services/inventario.py):
cada movimiento pasa por las reglas de stock, bloqueo de fila e idempotencia.

Es idempotente:
- proveedores y repuestos se buscan por nombre (sin distinguir mayúsculas)
  antes de crearlos;
- cada movimiento tiene una `clave_operacion` fija (`semilla-int:<id>:<n>`),
  así que volver a correr la semilla devuelve el movimiento original en vez de
  aplicarlo otra vez. Si una carga se cortó a medias, la siguiente la completa.

`verificar_existencias` comprueba que el stock de TODOS los repuestos coincida
con su historial de movimientos, y `diferencias_con_semilla` que los de
integración tengan el stock y lo comprometido de la semilla. Los usan el
script de semilla y las pruebas.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_integracion as integ
from services.ms3_presupuestos import datos_prueba
from services.ms3_presupuestos.models import MovimientoInventario, Repuesto
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.schemas.catalogo import RepuestoCrear
from services.ms3_presupuestos.schemas.inventario import MovimientoCrear
from services.ms3_presupuestos.services import catalogo, inventario

TIPOS_ADMINISTRADOR = {"ingreso", "ajuste"}


@dataclass
class ResumenCarga:
    proveedores_creados: list[str] = field(default_factory=list)
    repuestos_creados: list[str] = field(default_factory=list)
    movimientos_aplicados: int = 0
    movimientos_repetidos: int = 0
    umbral_general_creado: bool = False


def clave_movimiento(repuesto_id: int, numero: int) -> str:
    return f"semilla-int:{repuesto_id}:{numero}"


def cargar_integracion(
    sesion: Session,
    *,
    admin_id: int = datos_prueba.ADMIN_ID,
    mecanico_id: int = datos_prueba.MECANICO_ID,
    ordenes: Mapping[integ.PapelOrden, int] | None = None,
) -> ResumenCarga:
    problemas = integ.validar_catalogo()
    if problemas:
        raise ValueError("Catálogo de integración inválido: " + "; ".join(problemas))
    ordenes = {**integ.ORDENES_POR_DEFECTO, **(ordenes or {})}
    uow = UnidadDeTrabajo(sesion)
    resumen = ResumenCarga()

    # Sin umbral general vigente, las alertas por umbral general no se pueden probar.
    if uow.parametros.vigente() is None:
        inventario.cambiar_umbral_general(
            uow, valor=datos_prueba.UMBRAL_GENERAL, administrador_id=admin_id,
            observacion="Configuracion inicial del umbral general",
        )
        resumen.umbral_general_creado = True

    for prov in integ.CATALOGO_INTEGRACION:
        proveedor = uow.proveedores.con_nombre_similar(prov.nombre)
        if proveedor is None:
            proveedor = catalogo.crear_proveedor(uow, nombre=prov.nombre, contacto=prov.contacto,
                                                 tipo_distribuidor=prov.tipo_distribuidor)
            resumen.proveedores_creados.append(prov.nombre)

        for dato in prov.repuestos:
            repuesto = uow.repuestos.con_nombre_similar(proveedor.proveedor_id, dato.nombre)
            if repuesto is None:
                # Stock 0 al crear: las existencias vienen solo de los movimientos.
                repuesto = catalogo.crear_repuesto(uow, RepuestoCrear(
                    proveedor_id=proveedor.proveedor_id, nombre=dato.nombre,
                    stock_inicial=0, umbral_particular=dato.umbral_particular,
                ), administrador_id=admin_id)
                resumen.repuestos_creados.append(dato.nombre)

            for numero, mov in enumerate(dato.movimientos, start=1):
                resultado = inventario.registrar_movimiento(uow, MovimientoCrear(
                    clave_operacion=clave_movimiento(repuesto.repuesto_id, numero),
                    repuesto_id=repuesto.repuesto_id, tipo=mov.tipo, cantidad=mov.cantidad,
                    orden_id=ordenes[mov.orden] if mov.orden else None,
                ), usuario_id=admin_id if mov.tipo in TIPOS_ADMINISTRADOR else mecanico_id)
                if resultado.repetido:
                    resumen.movimientos_repetidos += 1
                else:
                    resumen.movimientos_aplicados += 1
    return resumen


def verificar_existencias(sesion: Session, *, nombres: Iterable[str] | None = None) -> list[str]:
    """Repuestos cuyo stock NO coincide con su historial de movimientos.

    Es una regla que debe cumplirse siempre (vacío = todo cuadra). Por defecto
    revisa todos los repuestos; con `nombres`, solo esos.
    """
    problemas: list[str] = []

    signo = case(
        (MovimientoInventario.tipo.in_(("ingreso", "ajuste")), MovimientoInventario.cantidad),
        (MovimientoInventario.tipo == "consumo", -MovimientoInventario.cantidad),
        else_=0,
    )
    por_movimientos = dict(sesion.execute(
        select(MovimientoInventario.repuesto_id, func.coalesce(func.sum(signo), 0))
        .group_by(MovimientoInventario.repuesto_id)
    ).all())
    consulta = select(Repuesto)
    if nombres is not None:
        consulta = consulta.where(Repuesto.nombre.in_(list(nombres)))
    repuestos = sesion.scalars(consulta).all()
    for r in repuestos:
        explicado = por_movimientos.get(r.repuesto_id, 0)
        if r.stock != explicado:
            problemas.append(f"{r.nombre}: stock {r.stock} pero los movimientos suman {explicado}")
    return problemas


def diferencias_con_semilla(
    sesion: Session, *, ordenes: Mapping[integ.PapelOrden, int] | None = None
) -> list[str]:
    """Repuestos de integración cuyo stock o comprometido ya no es el de la semilla.

    Justo después de cargarla debe estar vacía. Más adelante puede haber
    diferencias legítimas (alguien registró consumos al probar la app).
    """
    ordenes = {**integ.ORDENES_POR_DEFECTO, **(ordenes or {})}
    problemas: list[str] = []
    uow = UnidadDeTrabajo(sesion)
    por_nombre = {r.nombre: r for r in sesion.scalars(select(Repuesto))}
    for nombre, dato in integ.repuestos_integracion().items():
        r = por_nombre.get(nombre)
        if r is None:
            problemas.append(f"Falta el repuesto de integración {nombre!r}")
            continue
        if r.stock != dato.stock_esperado:
            problemas.append(f"{nombre}: stock {r.stock}, se esperaba {dato.stock_esperado}")
        esperado = {ordenes[papel]: c for papel, c in dato.comprometido_esperado().items()}
        real = {o: c for o, c in uow.movimientos.comprometido_por_orden(r.repuesto_id).items() if c}
        if real != esperado:
            problemas.append(f"{nombre}: comprometido {real}, se esperaba {esperado}")
    return problemas
