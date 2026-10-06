"""Casos de uso iniciales de presupuestos (Semana 5).

- crear_presupuesto: presupuesto lógico de una orden + versión 1 en borrador.
- listar_presupuestos / obtener_presupuesto / obtener_version: consultas.
- reemplazar_items: edita los ítems de una versión mientras es borrador.
- crear_version: versión siguiente sin sobrescribir las anteriores.
- enviar_version: congela la versión y la deja lista para el cliente.
- decidir_version: registra la aprobación o el rechazo del cliente.

Cada escritura es UNA transacción (`with uow.transaccion()`). Las reglas de
versionado las garantiza la base (triggers 0003_ms3); aquí se anticipan para
responder 409/422 con mensajes claros.

Enviar y decidir son operaciones TRANSACCIONALES: bloquean el presupuesto
(SELECT ... FOR UPDATE), validan, escriben y confirman todo junto; si algo
falla no queda nada a medias. Crear una versión también: bloquea el
presupuesto para que dos peticiones simultáneas no creen dos "versión 3".
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from decimal import Decimal

from sqlalchemy import func

from services.ms3_presupuestos.models import (
    DecisionPresupuesto,
    ItemPresupuesto,
    Presupuesto,
    VersionPresupuesto,
)
from services.ms3_presupuestos.persistencia import (
    ConflictoDeDatos,
    RecursoNoEncontrado,
    ReglaDeDatosViolada,
    UnidadDeTrabajo,
)
from services.ms3_presupuestos.schemas.presupuesto import (
    DecisionSalida,
    ItemEntrada,
    ItemSalida,
    PresupuestoDetalle,
    PresupuestoResumen,
    RepuestoFaltante,
    ResultadoOperacion,
    VersionDetalle,
)


# ---------------------------------------------------------------- escritura --

def crear_presupuesto(
    uow: UnidadDeTrabajo, *, orden_id: int, items: Sequence[ItemEntrada], creado_por_id: int
) -> Presupuesto:
    """Crea el único presupuesto de la orden con su versión 1 (borrador)."""
    with uow.transaccion():
        if uow.presupuestos.de_orden(orden_id) is not None:
            raise ConflictoDeDatos(
                f"La orden {orden_id} ya tiene presupuesto; las correcciones se "
                "registran como una nueva versión"
            )
        version = VersionPresupuesto(numero=1, creado_por_id=creado_por_id)
        version.items = _construir_items(uow, items)
        presupuesto = Presupuesto(orden_id=orden_id)
        presupuesto.versiones.append(version)
        uow.presupuestos.agregar(presupuesto)
    return presupuesto


def reemplazar_items(
    uow: UnidadDeTrabajo, *, presupuesto_id: int, numero: int, items: Sequence[ItemEntrada]
) -> VersionPresupuesto:
    """Reemplaza todos los ítems de una versión que sigue en borrador."""
    with uow.transaccion():
        uow.presupuestos.obtener_o_error(presupuesto_id)
        version = uow.presupuestos.version(presupuesto_id, numero)
        if not version.editable:
            raise ConflictoDeDatos(
                f"La versión {numero} ya fue enviada y no se puede modificar; "
                "las correcciones se registran como una nueva versión"
            )
        version.items.clear()
        uow.sesion.flush()  # borra los ítems anteriores antes de insertar
        version.items.extend(_construir_items(uow, items))
        uow.sesion.flush()
    return version


def crear_version(
    uow: UnidadDeTrabajo,
    *,
    presupuesto_id: int,
    creado_por_id: int,
    items: Sequence[ItemEntrada] | None = None,
    copiar_de: int | None = None,
) -> VersionPresupuesto:
    """Agrega la versión `n + 1` en borrador. Las versiones previas no se tocan.

    Reglas (§4.3):
    - Solo puede haber UN borrador abierto: si la última versión sigue en
      borrador, se edita esa (409).
    - Si el primer presupuesto fue rechazado (servicio cancelado), no hay más
      versiones: una nueva atención inicia otra orden y otro presupuesto (409).
    - Una corrección de una versión enviada sin decisión la REEMPLAZA: el
      cliente ya no puede decidir sobre la anterior (queda en el historial).
    - Tras una aprobación, la nueva versión es una MODIFICACIÓN
      (es_modificacion = true): mientras no se apruebe, manda la vigente.
    - Los ítems se copian como filas nuevas; jamás se mueven ni se editan
      los de otra versión (además lo impiden los triggers de 0003_ms3).
    """
    with uow.transaccion():
        presupuesto = uow.presupuestos.obtener_para_actualizar(presupuesto_id)
        ultima = presupuesto.versiones[-1]
        if not ultima.enviada:
            raise ConflictoDeDatos(
                f"La versión {ultima.numero} sigue en borrador; modifique esa versión "
                "en lugar de crear otra"
            )
        vigente = presupuesto.version_vigente
        decision = ultima.decision
        if vigente is None and decision is not None and decision.decision == "rechazado":
            raise ConflictoDeDatos(
                "El cliente rechazó el presupuesto y el servicio quedó cancelado; "
                "una nueva atención genera una nueva orden con su propio presupuesto"
            )

        if items is not None:
            nuevos_items = _construir_items(uow, items)
        else:
            base = (uow.presupuestos.version(presupuesto_id, copiar_de)
                    if copiar_de is not None else ultima)
            nuevos_items = [_copiar_item(i) for i in sorted(base.items, key=lambda i: i.item_id)]

        nueva = VersionPresupuesto(
            numero=presupuesto.siguiente_numero,
            creado_por_id=creado_por_id,
            es_modificacion=vigente is not None,
        )
        nueva.items = nuevos_items
        presupuesto.versiones.append(nueva)
        uow.sesion.flush()
    return nueva


def _copiar_item(item: ItemPresupuesto) -> ItemPresupuesto:
    """Fila NUEVA con los mismos datos (la original queda intacta en su versión)."""
    return ItemPresupuesto(
        tipo=item.tipo, descripcion=item.descripcion, cantidad=item.cantidad,
        precio_unitario=item.precio_unitario, repuesto_id=item.repuesto_id,
        repuesto=item.repuesto,
    )


def _construir_items(uow: UnidadDeTrabajo, items: Iterable[ItemEntrada]) -> list[ItemPresupuesto]:
    construidos = []
    for item in items:
        repuesto = None
        if item.repuesto_id is not None:
            repuesto = uow.repuestos.obtener(item.repuesto_id)
            if repuesto is None:
                raise ReglaDeDatosViolada(f"El repuesto {item.repuesto_id} no existe")
        construidos.append(ItemPresupuesto(
            tipo=item.tipo, descripcion=item.descripcion, cantidad=item.cantidad,
            precio_unitario=item.precio_unitario, repuesto=repuesto,
        ))
    return construidos


# ----------------------------------------------- operaciones transaccionales --

def enviar_version(uow: UnidadDeTrabajo, *, presupuesto_id: int, numero: int) -> ResultadoOperacion:
    """El administrador envía la versión al cliente: desde aquí queda congelada.

    Requisitos: es la última versión, sigue en borrador, tiene ítems y todos
    con precio (el administrador revisa y completa los importes, §4.3).
    Efecto: la primera vez (sin aprobación previa) la orden pasa a "Esperando
    aprobación de presupuesto"; una modificación posterior no cambia la orden.
    """
    with uow.transaccion():
        presupuesto = uow.presupuestos.obtener_para_actualizar(presupuesto_id)
        version = uow.presupuestos.version(presupuesto_id, numero)
        if version.enviada:
            raise ConflictoDeDatos(f"La versión {numero} ya fue enviada")
        _exigir_ultima(presupuesto, version)
        if not version.items:
            raise ReglaDeDatosViolada(f"La versión {numero} no tiene ítems; no se puede enviar")
        sin_precio = [i.descripcion for i in version.items if i.precio_unitario <= 0]
        if sin_precio:
            raise ReglaDeDatosViolada(
                "Complete el precio de estos ítems antes de enviar: " + ", ".join(sin_precio)
            )
        version.enviado_en = func.now()
        uow.sesion.flush()
        uow.sesion.refresh(version)
        efecto = None if presupuesto.version_vigente else "esperando_aprobacion"
    return ResultadoOperacion(presupuesto=a_detalle(presupuesto), efecto_en_orden=efecto)


def decidir_version(
    uow: UnidadDeTrabajo,
    *,
    presupuesto_id: int,
    numero: int,
    cliente_usuario_id: int,
    decision: str,
    motivo: str | None,
    confirmar_cancelacion: bool,
) -> ResultadoOperacion:
    """El cliente aprueba o rechaza la versión enviada (§4.3).

    - Solo la última versión, enviada y sin decisión previa.
    - Rechazar ANTES de la primera aprobación es rechazar el servicio: exige
      confirmar_cancelacion y el efecto es cancelar la orden.
    - Rechazar una modificación posterior conserva la aprobación vigente.
    - Aprobar bloquea la versión (trigger) y, según el stock de los repuestos,
      la orden pasa a "En reparación" o a "Esperando repuestos".
    """
    with uow.transaccion():
        presupuesto = uow.presupuestos.obtener_para_actualizar(presupuesto_id)
        version = uow.presupuestos.version(presupuesto_id, numero)
        if not version.enviada:
            raise ConflictoDeDatos(f"La versión {numero} aún no se envía al cliente")
        if version.decision is not None:
            raise ConflictoDeDatos(f"La versión {numero} ya tiene una decisión registrada")
        _exigir_ultima(presupuesto, version)

        primera_decision = presupuesto.version_vigente is None
        if decision == "rechazado" and primera_decision and not confirmar_cancelacion:
            raise ReglaDeDatosViolada(
                "Rechazar el presupuesto antes de la primera aprobación cancela el "
                "servicio; confirme con confirmar_cancelacion=true"
            )

        uow.sesion.add(DecisionPresupuesto(
            version=version, cliente_usuario_id=cliente_usuario_id,
            decision=decision, motivo=motivo or None,
        ))
        uow.sesion.flush()
        uow.sesion.refresh(version)  # bloqueada_en lo completa el trigger al aprobar

        faltantes: list[RepuestoFaltante] = []
        if decision == "aprobado":
            faltantes = _repuestos_faltantes(version)
            efecto = "esperando_repuestos" if faltantes else "en_reparacion"
        else:
            efecto = "cancelado" if primera_decision else None
    return ResultadoOperacion(
        presupuesto=a_detalle(presupuesto), efecto_en_orden=efecto,
        repuestos_faltantes=faltantes,
    )


def _exigir_ultima(presupuesto: Presupuesto, version: VersionPresupuesto) -> None:
    ultima = presupuesto.versiones[-1]
    if version.numero != ultima.numero:
        raise ConflictoDeDatos(
            f"La versión {version.numero} fue reemplazada por la versión {ultima.numero}"
        )


def _repuestos_faltantes(version: VersionPresupuesto) -> list[RepuestoFaltante]:
    """Repuestos de la versión cuyo stock no cubre la cantidad presupuestada."""
    requerido: dict[int, Decimal] = defaultdict(Decimal)
    repuestos = {}
    for item in version.items:
        if item.repuesto is not None:
            requerido[item.repuesto_id] += item.cantidad
            repuestos[item.repuesto_id] = item.repuesto
    return [
        RepuestoFaltante(repuesto_id=rid, nombre=repuestos[rid].nombre,
                         requerido=_dos_decimales(cantidad), disponible=repuestos[rid].stock)
        for rid, cantidad in sorted(requerido.items())
        if repuestos[rid].stock < cantidad
    ]


# ----------------------------------------------------------------- lectura --

def listar_presupuestos(
    uow: UnidadDeTrabajo, *, orden_id: int | None, desde: int, limite: int
) -> tuple[int, Sequence[Presupuesto]]:
    total = uow.presupuestos.contar_busqueda(orden_id=orden_id)
    return total, uow.presupuestos.buscar(orden_id=orden_id, desde=desde, limite=limite)


def obtener_presupuesto(uow: UnidadDeTrabajo, presupuesto_id: int) -> Presupuesto:
    return uow.presupuestos.obtener_o_error(presupuesto_id)


def obtener_version(
    uow: UnidadDeTrabajo, presupuesto_id: int, numero: int, *, solo_enviadas: bool = False
) -> VersionPresupuesto:
    uow.presupuestos.obtener_o_error(presupuesto_id)
    version = uow.presupuestos.version(presupuesto_id, numero)
    if solo_enviadas and not version.enviada:
        # El cliente no ve borradores: para él esa versión no existe todavía.
        raise RecursoNoEncontrado(f"El presupuesto {presupuesto_id} no tiene versión {numero}")
    return version


# ---------------------------------------------------- ORM → contrato HTTP --

def estado_version(version: VersionPresupuesto) -> str:
    if version.decision is not None:
        return "aprobada" if version.decision.decision == "aprobado" else "rechazada"
    return "enviada" if version.enviada else "borrador"


CENTAVOS = Decimal("0.01")


def _dos_decimales(valor: Decimal) -> Decimal:
    """Misma escala siempre (recién creado o leído de la base): 68990.00."""
    return Decimal(valor).quantize(CENTAVOS)


def total_version(version: VersionPresupuesto) -> Decimal:
    return _dos_decimales(sum((i.subtotal for i in version.items), Decimal("0")))


def a_version_detalle(version: VersionPresupuesto) -> VersionDetalle:
    return VersionDetalle(
        numero=version.numero,
        estado=estado_version(version),
        es_modificacion=version.es_modificacion,
        creado_por_id=version.creado_por_id,
        creado_en=version.creado_en,
        enviado_en=version.enviado_en,
        bloqueada_en=version.bloqueada_en,
        total=total_version(version),
        items=[_a_item(i) for i in sorted(version.items, key=lambda i: i.item_id)],
        decision=DecisionSalida.model_validate(version.decision) if version.decision else None,
    )


def _a_item(item: ItemPresupuesto) -> ItemSalida:
    repuesto = item.repuesto
    return ItemSalida(
        item_id=item.item_id, tipo=item.tipo, descripcion=item.descripcion,
        cantidad=_dos_decimales(item.cantidad),
        precio_unitario=_dos_decimales(item.precio_unitario),
        subtotal=_dos_decimales(item.subtotal), repuesto_id=item.repuesto_id,
        repuesto_nombre=repuesto.nombre if repuesto else None,
        proveedor_nombre=repuesto.proveedor.nombre if repuesto else None,
    )


def _datos_resumen(
    presupuesto: Presupuesto, versiones: Sequence[VersionPresupuesto] | None = None
) -> dict:
    versiones = presupuesto.versiones if versiones is None else versiones
    if not versiones:
        # Para el cliente, un presupuesto que solo tiene borradores no existe aún.
        raise RecursoNoEncontrado(f"Presupuesto {presupuesto.presupuesto_id} no existe")
    ultima = versiones[-1]
    vigente = presupuesto.version_vigente
    return {
        "presupuesto_id": presupuesto.presupuesto_id,
        "orden_id": presupuesto.orden_id,
        "creado_en": presupuesto.creado_en,
        "cantidad_versiones": len(versiones),
        "ultima_version": ultima.numero,
        "estado_ultima_version": estado_version(ultima),
        "total_ultima_version": total_version(ultima),
        "version_vigente": vigente.numero if vigente else None,
    }


def a_resumen(presupuesto: Presupuesto, *, solo_enviadas: bool = False) -> PresupuestoResumen:
    versiones = [v for v in presupuesto.versiones if v.enviada or not solo_enviadas]
    return PresupuestoResumen(**_datos_resumen(presupuesto, versiones))


def a_detalle(presupuesto: Presupuesto, *, solo_enviadas: bool = False) -> PresupuestoDetalle:
    versiones = [v for v in presupuesto.versiones if v.enviada or not solo_enviadas]
    datos = _datos_resumen(presupuesto, versiones)
    return PresupuestoDetalle(**datos, versiones=[a_version_detalle(v) for v in versiones])
