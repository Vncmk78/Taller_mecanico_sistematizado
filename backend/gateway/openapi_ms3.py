"""Documentación OpenAPI de MS3 (Presupuestos, Repuestos, Proveedores e Inventario).

Complementa `gateway/openapi.py` con los endpoints que la Gateway enruta hacia
MS3 por los prefijos `presupuestos`, `repuestos`, `proveedores` e `inventario`.
Usa las mismas piezas que el resto del Swagger de la Gateway (`_operacion`,
`ErrorRespuesta`/`ErrorDetalle`, respuestas reutilizables) y las copias de los
contratos de `gateway/contratos/{presupuestos,catalogo,inventario}.py`; la
Gateway no importa código de MS3.

Cada operación se declara en una tabla (`_OPERACIONES`) con su resumen, roles,
body, respuesta de éxito, errores propios de MS3 y un ejemplo real de éxito.
`tests/test_gateway_openapi.py` comprueba que todos los endpoints de MS3
quedan documentados y `tests/test_gateway_openapi_ejemplos.py` que cada ejemplo
cumple su esquema.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from gateway.contratos import catalogo as contratos_catalogo
from gateway.contratos import inventario as contratos_inventario
from gateway.contratos import presupuestos as contratos_presupuestos
from gateway.openapi import (
    _PARAMETRO_ORDEN_ID,
    _operacion,
    _ref,
    _respuesta,
)
from shared.contratos_decisiones import (
    AplicacionEnvioPresupuestoRespuesta,
    AprobacionInicialOrdenVerificada,
    EnvioPresupuestoAplicacionPendiente,
    EnvioPresupuestoVerificado,
)

_JSON = "application/json"
_FECHA = "2026-10-20T09:15:00-03:00"
_FECHA_2 = "2026-10-21T16:40:00-03:00"

# Contratos de MS3 que se publican en `components.schemas` (con sus anidados).
CONTRATOS_MS3: tuple[type[BaseModel], ...] = (
    contratos_presupuestos.PresupuestoCrear,
    contratos_presupuestos.ItemsVersion,
    contratos_presupuestos.NuevaVersion,
    contratos_presupuestos.DecisionEntrada,
    contratos_presupuestos.PresupuestoDetalle,
    contratos_presupuestos.PaginaPresupuestos,
    contratos_presupuestos.VersionDetalle,
    contratos_presupuestos.ResultadoOperacion,
    contratos_catalogo.ProveedorCrear,
    contratos_catalogo.ProveedorActualizar,
    contratos_catalogo.ProveedorSalida,
    contratos_catalogo.ProveedorDetalle,
    contratos_catalogo.PaginaProveedores,
    contratos_catalogo.RepuestoCrear,
    contratos_catalogo.RepuestoActualizar,
    contratos_catalogo.RepuestoSalida,
    contratos_catalogo.PaginaRepuestos,
    contratos_catalogo.TrazabilidadRepuesto,
    contratos_catalogo.TrazabilidadProveedor,
    contratos_inventario.MovimientoCrear,
    contratos_inventario.ResultadoMovimiento,
    contratos_inventario.PaginaMovimientos,
    contratos_inventario.StockSalida,
    contratos_inventario.PaginaAlertas,
    contratos_inventario.UmbralGeneralEntrada,
    contratos_inventario.UmbralGeneralSalida,
    contratos_inventario.CambioUmbral,
    contratos_inventario.ConsultaDisponibilidad,
    contratos_inventario.ResultadoDisponibilidad,
    contratos_inventario.RechazoStock,
    contratos_inventario.ConsumoOrden,
    contratos_inventario.LiberacionOrden,
    contratos_inventario.ResultadoOperacionOrden,
    contratos_inventario.ResultadoReserva,
    AprobacionInicialOrdenVerificada,
    EnvioPresupuestoVerificado,
    AplicacionEnvioPresupuestoRespuesta,
    EnvioPresupuestoAplicacionPendiente,
)


def esquemas_ms3() -> dict[str, dict[str, Any]]:
    """Esquemas JSON de los contratos de MS3 y de todos sus modelos anidados."""
    _, definiciones = models_json_schema(
        [(modelo, "validation") for modelo in CONTRATOS_MS3],
        ref_template="#/components/schemas/{model}",
    )
    return definiciones.get("$defs", {})


# ------------------------------------------------------------- parámetros --


def _path(nombre: str, descripcion: str, ejemplo: Any, esquema: dict | None = None) -> dict:
    return {
        "name": nombre,
        "in": "path",
        "required": True,
        "description": descripcion,
        "schema": {**(esquema or {"type": "integer", "exclusiveMinimum": 0}), "example": ejemplo},
    }


def _query(nombre: str, descripcion: str, esquema: dict) -> dict:
    return {"name": nombre, "in": "query", "required": False,
            "description": descripcion, "schema": esquema}


_P_PRESUPUESTO = _path("presupuesto_id", "Identificador del presupuesto.", 7)
_P_NUMERO = _path("numero", "Número de versión (1, 2, ...).", 1)
_P_DECISION = _path("decision_id", "Identificador de la decisión del cliente.", 9)
_P_REPUESTO = _path("repuesto_id", "Identificador del repuesto.", 12)
_P_PROVEEDOR = _path("proveedor_id", "Identificador del proveedor.", 3)

_ENTERO_OPCIONAL = {"type": "integer", "exclusiveMinimum": 0}
_DESDE = _query("desde", "Desplazamiento de la paginación.", {"type": "integer", "minimum": 0, "default": 0})
_LIMITE = _query("limite", "Máximo de elementos por página.", {"type": "integer", "minimum": 1, "maximum": 200, "default": 50})
_BUSQUEDA = _query("q", "Texto a buscar en el nombre.", {"type": "string", "maxLength": 120})

# --------------------------------------------------------------- ejemplos --

_PROVEEDOR_BREVE = {"proveedor_id": 3, "nombre": "Repuestos del Sur", "tipo_distribuidor": "oficial"}
_PROVEEDOR = {
    "proveedor_id": 3,
    "nombre": "Repuestos del Sur",
    "contacto": "ventas@repuestosdelsur.cl",
    "tipo_distribuidor": "oficial",
    "cantidad_repuestos": 1,
}
_REPUESTO = {
    "repuesto_id": 12,
    "nombre": "Pastillas de freno delanteras",
    "proveedor_id": 3,
    "proveedor_nombre": "Repuestos del Sur",
    "proveedor_tipo_distribuidor": "oficial",
    "stock": 8,
    "umbral_particular": None,
    "umbral_efectivo": 5,
    "bajo_umbral": False,
}
_MOVIMIENTO = {
    "movimiento_id": 101,
    "clave_operacion": "ingreso-2026-10-20-0001",
    "repuesto_id": 12,
    "tipo": "ingreso",
    "cantidad": 10,
    "orden_id": None,
    "proveedor_id": 3,
    "fecha_hora": _FECHA,
    "registrado_por_id": 1,
}
_MOVIMIENTO_COMPROMISO = {**_MOVIMIENTO, "movimiento_id": 102, "tipo": "compromiso",
                          "clave_operacion": "reserva-orden-31-v1", "cantidad": 2,
                          "orden_id": 31, "proveedor_id": None}
_MOVIMIENTO_CONSUMO = {**_MOVIMIENTO_COMPROMISO, "movimiento_id": 103, "tipo": "consumo",
                       "clave_operacion": "consumo-orden-31-0001"}
_STOCK = {
    "repuesto_id": 12,
    "nombre": "Pastillas de freno delanteras",
    "proveedor_nombre": "Repuestos del Sur",
    "stock": 8,
    "comprometido": 2,
    "disponible": 6,
    "umbral_efectivo": 5,
    "bajo_umbral": False,
    "compromisos": [{"orden_id": 31, "comprometido": 2}],
}
_FALTANTE = {"repuesto_id": 12, "nombre": "Pastillas de freno delanteras",
             "solicitado": 4, "disponible": 3, "faltan": 1}
_DISPONIBILIDAD = {
    "orden_id": 31,
    "disponible": False,
    "repuestos": [{
        "repuesto_id": 12,
        "nombre": "Pastillas de freno delanteras",
        "proveedor_nombre": "Repuestos del Sur",
        "requerido": 4,
        "stock": 8,
        "reservado_para_orden": 0,
        "comprometido_otras_ordenes": 5,
        "disponible": 3,
        "alcanza": False,
        "faltan": 1,
    }],
    "presupuesto_id": None,
    "version": None,
}
_ITEM_REPUESTO = {
    "item_id": 501,
    "tipo": "repuesto",
    "descripcion": "Pastillas de freno delanteras",
    "cantidad": "1.00",
    "precio_unitario": "38990.00",
    "subtotal": "38990.00",
    "repuesto_id": 12,
    "repuesto_nombre": "Pastillas de freno delanteras",
    "proveedor_nombre": "Repuestos del Sur",
}
_ITEM_MANO_OBRA = {
    "item_id": 502,
    "tipo": "mano_de_obra",
    "descripcion": "Cambio de pastillas",
    "cantidad": "1.00",
    "precio_unitario": "25000.00",
    "subtotal": "25000.00",
    "repuesto_id": None,
    "repuesto_nombre": None,
    "proveedor_nombre": None,
}
_VERSION_BORRADOR = {
    "numero": 1,
    "estado": "borrador",
    "es_modificacion": False,
    "creado_por_id": 5,
    "creado_en": _FECHA,
    "enviado_en": None,
    "bloqueada_en": None,
    "total": "63990.00",
    "items": [_ITEM_REPUESTO, _ITEM_MANO_OBRA],
    "decision": None,
}
_VERSION_ENVIADA = {**_VERSION_BORRADOR, "estado": "enviada",
                    "enviado_en": _FECHA_2, "bloqueada_en": _FECHA_2}
_VERSION_APROBADA = {**_VERSION_ENVIADA, "estado": "aprobada", "decision": {
    "decision_id": 9, "decision": "aprobado", "cliente_usuario_id": 42,
    "fecha_hora": _FECHA_2, "motivo": None,
}}
_RESUMEN = {
    "presupuesto_id": 7,
    "orden_id": 31,
    "creado_en": _FECHA,
    "cantidad_versiones": 1,
    "ultima_version": 1,
    "estado_ultima_version": "borrador",
    "total_ultima_version": "63990.00",
    "version_vigente": None,
}
_DETALLE_BORRADOR = {**_RESUMEN, "versiones": [_VERSION_BORRADOR]}
_DETALLE_ENVIADO = {**_RESUMEN, "estado_ultima_version": "enviada", "versiones": [_VERSION_ENVIADA]}
_DETALLE_APROBADO = {**_RESUMEN, "estado_ultima_version": "aprobada", "version_vigente": 1,
                     "versiones": [_VERSION_APROBADA]}
_APLICACION_ENVIO = {"presupuesto_id": 7, "orden_id": 31, "estado_aplicado": 3, "historial_id": 40}
_ITEMS_ENTRADA = [
    {"tipo": "repuesto", "descripcion": "Pastillas de freno delanteras",
     "cantidad": "1", "precio_unitario": "38990", "repuesto_id": 12},
    {"tipo": "mano_de_obra", "descripcion": "Cambio de pastillas",
     "cantidad": "1", "precio_unitario": "25000"},
]


def _ejemplo(valor: Any, resumen: str | None = None) -> dict[str, Any]:
    ejemplo: dict[str, Any] = {"value": deepcopy(valor)}
    if resumen:
        ejemplo["summary"] = resumen
    return ejemplo


# ------------------------------------------------------------ operaciones --

_ROLES_CATALOGO = "Mecánico o Administrador consultan; solo Administrador crea, modifica o elimina."
_MS2_NO_DISPONIBLE = "MS2 no disponible para validar la orden"


@dataclass
class _Op:
    ruta: str
    metodo: str
    tag: str
    operation_id: str
    resumen: str
    descripcion: str
    exito: str
    respuesta: dict[str, Any] | None
    ejemplo: Any
    errores: dict[str, str]
    parametros: list[dict] = field(default_factory=list)
    cuerpo: str | None = None
    ejemplo_cuerpo: Any = None
    cuerpo_opcional: bool = False
    con_orden_id: bool = False
    # 503 propio de MS3 (MS2 caído o coordinación pendiente): esquema del body.
    esquema_503: str | None = None
    descripcion_404: str = "Recurso inexistente o no visible para el usuario."
    extra_respuestas: dict[str, dict[str, Any]] = field(default_factory=dict)


_OPERACIONES: tuple[_Op, ...] = (
    # ------------------------------------------------------- presupuestos --
    _Op("/api/presupuestos", "post", "Presupuestos", "crear_presupuesto",
        "Crear el presupuesto de una orden",
        "Mecánico o Administrador. Crea el presupuesto lógico de la orden con su "
        "versión 1 en borrador. El mecánico puede proponer ítems sin precio; el "
        "administrador completa los importes antes de enviar. MS3 consulta MS2 con "
        "el JWT original: exige orden existente y asignación al Mecánico, incluso "
        "si además es Cliente propietario. Administrador no requiere asignación. "
        "Orden inexistente o no asignada: 404; MS2 no verificable: 503, sin escrituras.",
        "201", _ref("PresupuestoDetalle"), _DETALLE_BORRADOR,
        {"401": "JWT ausente o inválido", "403": "Se requiere rol Mecánico o Administrador",
         "409": "La orden ya tiene presupuesto", "422": "Ítems inválidos o repuesto inexistente"},
        cuerpo="PresupuestoCrear", ejemplo_cuerpo={"orden_id": 31, "items": _ITEMS_ENTRADA},
        esquema_503="ErrorDetalle", descripcion_404="Orden inexistente o no asignada al Mecánico."),
    _Op("/api/presupuestos", "get", "Presupuestos", "listar_presupuestos",
        "Listar presupuestos o buscar el de una orden",
        "Más recientes primero. El Cliente debe indicar `orden_id` de una orden suya "
        "y solo ve versiones enviadas.",
        "200", _ref("PaginaPresupuestos"),
        {"total": 1, "desde": 0, "limite": 50, "presupuestos": [_RESUMEN]},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Parámetros inválidos"},
        parametros=[_query("orden_id", "Filtra por orden de trabajo.", _ENTERO_OPCIONAL), _DESDE, _LIMITE],
        esquema_503="ErrorDetalle"),
    _Op("/api/presupuestos/ordenes/{orden_id}/primera-aprobacion", "get", "Presupuestos",
        "consultar_aprobacion_inicial_orden",
        "Comprobar si una orden tiene una aprobación inicial persistida",
        "Administrador o Cliente propietario. Consulta el registro de MS3, incluso si "
        "MS2 aún no alcanzó a aplicar la transición.",
        "200", _ref("AprobacionInicialOrdenVerificada"),
        {"orden_id": 31, "aprobacion_registrada": True},
        {"401": "JWT ausente o inválido", "403": "Se requiere Administrador o Cliente propietario",
         "422": "Identificador inválido"},
        con_orden_id=True, esquema_503="ErrorDetalle",
        descripcion_404="Orden sin presupuesto o ajena."),
    _Op("/api/presupuestos/{presupuesto_id}", "get", "Presupuestos", "detalle_presupuesto",
        "Detalle de un presupuesto con sus versiones",
        "El Cliente solo ve presupuestos de sus órdenes y solo las versiones enviadas.",
        "200", _ref("PresupuestoDetalle"), _DETALLE_ENVIADO,
        {"401": "JWT ausente o inválido", "422": "Identificador inválido"},
        parametros=[_P_PRESUPUESTO], esquema_503="ErrorDetalle",
        descripcion_404="Presupuesto inexistente o ajeno."),
    _Op("/api/presupuestos/{presupuesto_id}/versiones/{numero}", "get", "Presupuestos",
        "version_presupuesto", "Una versión del presupuesto con sus ítems y decisión",
        "Misma visibilidad que el detalle del presupuesto.",
        "200", _ref("VersionDetalle"), _VERSION_ENVIADA,
        {"401": "JWT ausente o inválido", "422": "Identificador inválido"},
        parametros=[_P_PRESUPUESTO, _P_NUMERO], esquema_503="ErrorDetalle",
        descripcion_404="Presupuesto o versión inexistente (o ajeno)."),
    _Op("/api/presupuestos/{presupuesto_id}/versiones", "post", "Presupuestos",
        "crear_version_presupuesto", "Crear la versión siguiente sin sobrescribir las anteriores",
        "Mecánico o Administrador. Corrige una versión enviada o propone una modificación "
        "tras una aprobación. Sin body (o sin `items`) copia los ítems de la última versión "
        "o de `copiar_de`; las versiones previas quedan intactas en el historial.",
        "201", _ref("PresupuestoDetalle"),
        {**_DETALLE_ENVIADO, "cantidad_versiones": 2, "ultima_version": 2,
         "estado_ultima_version": "borrador",
         "versiones": [_VERSION_ENVIADA, {**_VERSION_BORRADOR, "numero": 2}]},
        {"401": "JWT ausente o inválido", "403": "Se requiere rol Mecánico o Administrador",
         "409": "Ya hay un borrador abierto o el servicio fue cancelado",
         "422": "Ítems inválidos o repuesto inexistente"},
        parametros=[_P_PRESUPUESTO], cuerpo="NuevaVersion", ejemplo_cuerpo={"copiar_de": 1},
        cuerpo_opcional=True, descripcion_404="Presupuesto inexistente o ajeno."),
    _Op("/api/presupuestos/{presupuesto_id}/versiones/{numero}/items", "put", "Presupuestos",
        "reemplazar_items_version", "Reemplazar los ítems de una versión en borrador",
        "Mecánico o Administrador. Reemplaza la lista completa de ítems; una versión "
        "enviada queda congelada (409).",
        "200", _ref("VersionDetalle"), _VERSION_BORRADOR,
        {"401": "JWT ausente o inválido", "403": "Se requiere rol Mecánico o Administrador",
         "409": "La versión ya fue enviada (congelada)",
         "422": "Ítems inválidos o repuesto inexistente"},
        parametros=[_P_PRESUPUESTO, _P_NUMERO], cuerpo="ItemsVersion",
        ejemplo_cuerpo={"items": _ITEMS_ENTRADA},
        descripcion_404="Presupuesto o versión inexistente (o ajeno)."),
    _Op("/api/presupuestos/{presupuesto_id}/versiones/{numero}/envio", "post", "Presupuestos",
        "enviar_version_presupuesto", "Enviar la versión al cliente (queda congelada)",
        "Solo Administrador. La versión debe ser la última, estar en borrador y tener ítems "
        "con precio. El primer envío coordina con MS2 la transición de la orden "
        "(`efecto_en_orden: esperando_aprobacion` y `aplicacion_en_orden`). Si la "
        "coordinación falla, el envío queda guardado y se responde 503 con una ruta de "
        "reintento idempotente.",
        "200", _ref("ResultadoOperacion"),
        {"presupuesto": _DETALLE_ENVIADO, "efecto_en_orden": "esperando_aprobacion",
         "repuestos_faltantes": [], "repuestos_reservados": {}, "decision_id": None,
         "aplicacion_en_orden": _APLICACION_ENVIO},
        {"401": "JWT ausente o inválido", "403": "Se requiere rol Administrador",
         "409": "Ya enviada o no es la última versión",
         "422": "Sin ítems o con ítems sin precio"},
        parametros=[_P_PRESUPUESTO, _P_NUMERO], esquema_503="EnvioPresupuestoAplicacionPendiente",
        descripcion_404="Presupuesto o versión inexistente (o ajeno)."),
    _Op("/api/presupuestos/{presupuesto_id}/envio-inicial", "get", "Presupuestos",
        "verificar_envio_inicial", "Verificar el envío inicial (coordinación con MS2)",
        "Lo consulta MS2 con el JWT original antes de pasar la orden a 'Esperando "
        "aprobación'. Responde el hecho persistido del primer envío.",
        "200", _ref("EnvioPresupuestoVerificado"),
        {"presupuesto_id": 7, "orden_id": 31, "envio_inicial_confirmado": True},
        {"401": "JWT ausente o inválido", "409": "No hay envío inicial pendiente",
         "422": "Identificador inválido"},
        parametros=[_P_PRESUPUESTO], descripcion_404="Presupuesto inexistente o ajeno."),
    _Op("/api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion", "post", "Presupuestos",
        "reintentar_aplicacion_envio", "Reintentar la aplicación del envío inicial en MS2",
        "Solo Administrador. No vuelve a enviar la versión ni crea otro evento; si MS2 ya "
        "confirmó, devuelve la aplicación existente. Si la verificación sigue fallando "
        "responde 503 y conserva el envío para un nuevo reintento.",
        "200", _ref("AplicacionEnvioPresupuestoRespuesta"), _APLICACION_ENVIO,
        {"401": "JWT ausente o inválido", "403": "Se requiere rol Administrador",
         "409": "El envío no está pendiente de aplicación", "422": "Identificador inválido"},
        parametros=[_P_PRESUPUESTO], esquema_503="EnvioPresupuestoAplicacionPendiente",
        descripcion_404="Presupuesto inexistente o ajeno."),
    _Op("/api/presupuestos/{presupuesto_id}/versiones/{numero}/decision", "post", "Presupuestos",
        "decidir_presupuesto", "Aprobar o rechazar la versión enviada",
        "Solo el Cliente dueño de la orden. Todo rechazo exige `motivo`; rechazar antes "
        "de la primera aprobación cancela el servicio y exige `confirmar_cancelacion: "
        "true`. Aprobar deja la orden en `en_reparacion` o `esperando_repuestos` según el "
        "stock. Un 503 con `decision_id` permite reintentar la aplicación sin volver a "
        "decidir.",
        "201", _ref("ResultadoOperacion"),
        {"presupuesto": _DETALLE_APROBADO, "efecto_en_orden": "en_reparacion",
         "repuestos_faltantes": [], "repuestos_reservados": {"12": 1}, "decision_id": 9,
         "aplicacion_en_orden": {"decision_id": 9, "orden_id": 31, "estado_aplicado": 5,
                                 "historial_id": 41}},
        {"401": "JWT ausente o inválido", "403": "Se requiere rol Cliente",
         "409": "No enviada, ya decidida o reemplazada",
         "422": "Rechazo sin motivo o sin confirmar la cancelación"},
        parametros=[_P_PRESUPUESTO, _P_NUMERO], cuerpo="DecisionEntrada",
        ejemplo_cuerpo={"decision": "aprobado"}, esquema_503="DecisionAplicacionPendiente",
        descripcion_404="Presupuesto o versión inexistente (o ajeno)."),
    # ---------------------------------------------------------- repuestos --
    _Op("/api/repuestos", "get", "Repuestos", "listar_repuestos", "Listar o buscar repuestos",
        _ROLES_CATALOGO + " Incluye el umbral general vigente y si cada repuesto está bajo "
        "su umbral efectivo.",
        "200", _ref("PaginaRepuestos"),
        {"total": 1, "desde": 0, "limite": 50, "umbral_general": 5, "repuestos": [_REPUESTO]},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Parámetros inválidos"},
        parametros=[
            _query("proveedor_id", "Solo los del proveedor.", _ENTERO_OPCIONAL), _BUSQUEDA,
            _query("bajo_umbral", "Solo los que están bajo su umbral.", {"type": "boolean", "default": False}),
            _query("con_stock", "true: con stock; false: sin stock.", {"type": "boolean"}),
            _query("ordenar", "Campo de orden.", {"type": "string", "default": "nombre"}),
            _DESDE, _LIMITE,
        ]),
    _Op("/api/repuestos", "post", "Repuestos", "crear_repuesto",
        "Registrar un repuesto",
        "Solo Administrador. El stock inicial queda respaldado por un movimiento de "
        "ingreso; sin `umbral_particular` se aplica el umbral general.",
        "201", _ref("RepuestoSalida"), _REPUESTO,
        {"401": "JWT ausente o inválido", "403": "Rol no permitido",
         "409": "Nombre repetido en el proveedor", "422": "Datos inválidos"},
        cuerpo="RepuestoCrear",
        ejemplo_cuerpo={"proveedor_id": 3, "nombre": "Pastillas de freno delanteras", "stock_inicial": 8},
        descripcion_404="Proveedor inexistente."),
    _Op("/api/repuestos/{repuesto_id}", "get", "Repuestos", "detalle_repuesto",
        "Detalle de un repuesto", _ROLES_CATALOGO,
        "200", _ref("RepuestoSalida"), _REPUESTO,
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Identificador inválido"},
        parametros=[_P_REPUESTO], descripcion_404="Repuesto inexistente."),
    _Op("/api/repuestos/{repuesto_id}", "patch", "Repuestos", "actualizar_repuesto",
        "Modificar nombre, proveedor o umbral particular",
        "Solo Administrador. El stock no se modifica aquí (solo con movimientos). "
        "`umbral_particular: null` vuelve al umbral general; el cambio queda en el historial.",
        "200", _ref("RepuestoSalida"), {**_REPUESTO, "umbral_particular": 4, "umbral_efectivo": 4},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido",
         "409": "Nombre repetido en el proveedor", "422": "Datos inválidos"},
        parametros=[_P_REPUESTO], cuerpo="RepuestoActualizar",
        ejemplo_cuerpo={"umbral_particular": 4, "observacion": "Rotación alta"},
        descripcion_404="Repuesto o proveedor inexistente."),
    _Op("/api/repuestos/{repuesto_id}", "delete", "Repuestos", "eliminar_repuesto",
        "Eliminar un repuesto que nunca se usó",
        "Solo Administrador. Un repuesto con movimientos o presupuestos responde 409.",
        "204", None, None,
        {"401": "JWT ausente o inválido", "403": "Rol no permitido",
         "409": "Repuesto con historial", "422": "Identificador inválido"},
        parametros=[_P_REPUESTO], descripcion_404="Repuesto inexistente."),
    _Op("/api/repuestos/{repuesto_id}/trazabilidad", "get", "Repuestos", "trazabilidad_repuesto",
        "Trazabilidad repuesto–proveedor",
        "Proveedor actual, historial de proveedores, ingresos por proveedor y uso por orden. "
        + _ROLES_CATALOGO.split(";")[0] + ".",
        "200", _ref("TrazabilidadRepuesto"),
        {"repuesto": _REPUESTO, "proveedor_actual": _PROVEEDOR_BREVE,
         "historial_proveedores": [{"proveedor_anterior": None, "proveedor_nuevo": _PROVEEDOR_BREVE,
                                    "fecha_hora": _FECHA, "registrado_por_id": 1, "observacion": None}],
         "ingresos_por_proveedor": [{"proveedor": _PROVEEDOR_BREVE, "ingresos": 2, "unidades": 10,
                                     "primer_ingreso": _FECHA, "ultimo_ingreso": _FECHA_2}],
         "uso_por_orden": [{"orden_id": 31, "reservado": 0, "consumido": 2}]},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Identificador inválido"},
        parametros=[_P_REPUESTO], descripcion_404="Repuesto inexistente."),
    # -------------------------------------------------------- proveedores --
    _Op("/api/proveedores", "get", "Proveedores", "listar_proveedores",
        "Listar o buscar proveedores", _ROLES_CATALOGO,
        "200", _ref("PaginaProveedores"),
        {"total": 1, "desde": 0, "limite": 50, "proveedores": [_PROVEEDOR]},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Parámetros inválidos"},
        parametros=[
            _BUSQUEDA,
            _query("con_repuestos", "true: con repuestos; false: sin repuestos.", {"type": "boolean"}),
            _query("tipo_distribuidor", "Oficial de la marca o genérico.",
                   {"type": "string", "enum": ["oficial", "generico"]}),
            _DESDE, _LIMITE,
        ]),
    _Op("/api/proveedores", "post", "Proveedores", "crear_proveedor", "Registrar un proveedor",
        "Solo Administrador.",
        "201", _ref("ProveedorSalida"), {**_PROVEEDOR, "cantidad_repuestos": 0},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido",
         "409": "Nombre repetido", "422": "Datos inválidos"},
        cuerpo="ProveedorCrear",
        ejemplo_cuerpo={"nombre": "Repuestos del Sur", "contacto": "ventas@repuestosdelsur.cl",
                        "tipo_distribuidor": "oficial"}),
    _Op("/api/proveedores/{proveedor_id}", "get", "Proveedores", "detalle_proveedor",
        "Detalle del proveedor con sus repuestos", _ROLES_CATALOGO,
        "200", _ref("ProveedorDetalle"), {**_PROVEEDOR, "repuestos": [_REPUESTO]},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Identificador inválido"},
        parametros=[_P_PROVEEDOR], descripcion_404="Proveedor inexistente."),
    _Op("/api/proveedores/{proveedor_id}", "patch", "Proveedores", "actualizar_proveedor",
        "Modificar nombre, contacto y/o tipo de distribuidor", "Solo Administrador.",
        "200", _ref("ProveedorSalida"), {**_PROVEEDOR, "contacto": "+56 9 1234 5678"},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido",
         "409": "Nombre repetido", "422": "Datos inválidos"},
        parametros=[_P_PROVEEDOR], cuerpo="ProveedorActualizar",
        ejemplo_cuerpo={"contacto": "+56 9 1234 5678"}, descripcion_404="Proveedor inexistente."),
    _Op("/api/proveedores/{proveedor_id}", "delete", "Proveedores", "eliminar_proveedor",
        "Eliminar un proveedor sin repuestos",
        "Solo Administrador. Un proveedor con repuestos o con trazabilidad registrada responde 409.",
        "204", None, None,
        {"401": "JWT ausente o inválido", "403": "Rol no permitido",
         "409": "Proveedor con repuestos o con trazabilidad registrada",
         "422": "Identificador inválido"},
        parametros=[_P_PROVEEDOR], descripcion_404="Proveedor inexistente."),
    _Op("/api/proveedores/{proveedor_id}/trazabilidad", "get", "Proveedores",
        "trazabilidad_proveedor", "Repuestos que el proveedor abastece o abasteció",
        "Con las unidades entregadas por cada repuesto (`actual: false` si ya no lo abastece).",
        "200", _ref("TrazabilidadProveedor"),
        {"proveedor": _PROVEEDOR_BREVE, "unidades_ingresadas": 10,
         "repuestos": [{"repuesto_id": 12, "nombre": "Pastillas de freno delanteras",
                        "actual": True, "unidades_ingresadas": 10}]},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Identificador inválido"},
        parametros=[_P_PROVEEDOR], descripcion_404="Proveedor inexistente."),
    # --------------------------------------------------------- inventario --
    _Op("/api/inventario/movimientos", "post", "Inventario", "registrar_movimiento",
        "Registrar un movimiento de stock",
        "Ingreso y ajuste: Administrador. Compromiso, consumo y liberación: Mecánico o "
        "Administrador, siempre con `orden_id`. Reenviar la misma `clave_operacion` "
        "devuelve el movimiento original con 200 y `repetido: true` (no se aplica dos veces).",
        "201", _ref("ResultadoMovimiento"),
        {"movimiento": _MOVIMIENTO, "stock": {**_STOCK, "stock": 18, "disponible": 16},
         "alerta": {"activa": False, "nueva": False}, "repetido": False},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Datos inválidos"},
        cuerpo="MovimientoCrear",
        ejemplo_cuerpo={"clave_operacion": "ingreso-2026-10-20-0001", "repuesto_id": 12,
                        "tipo": "ingreso", "cantidad": 10, "proveedor_id": 3},
        descripcion_404="Repuesto inexistente.",
        extra_respuestas={
            "200": _respuesta("Clave repetida: se devuelve el movimiento original.",
                              _ref("ResultadoMovimiento")),
            "409": _respuesta("Stock insuficiente (con `faltantes`), liberación mayor a lo "
                              "comprometido o clave usada con otros datos.",
                              {"oneOf": [_ref("RechazoStock"), _ref("ErrorDetalle")]}),
        }),
    _Op("/api/inventario/movimientos", "get", "Inventario", "listar_movimientos",
        "Movimientos de stock (más recientes primero)",
        "Mecánico o Administrador.",
        "200", _ref("PaginaMovimientos"),
        {"total": 1, "desde": 0, "limite": 50, "movimientos": [_MOVIMIENTO]},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Parámetros inválidos"},
        parametros=[
            _query("repuesto_id", "Solo los del repuesto.", _ENTERO_OPCIONAL),
            _query("orden_id", "Solo los de la orden.", _ENTERO_OPCIONAL),
            _query("tipo", "Tipo de movimiento.",
                   {"type": "string", "enum": ["ingreso", "ajuste", "compromiso", "consumo", "liberacion"]}),
            _query("proveedor_id", "Solo los ingresos del proveedor.", _ENTERO_OPCIONAL),
            _DESDE, _LIMITE,
        ]),
    _Op("/api/inventario/stock/{repuesto_id}", "get", "Inventario", "stock_repuesto",
        "Stock físico, comprometido por orden y disponible", "Mecánico o Administrador.",
        "200", _ref("StockSalida"), _STOCK,
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Identificador inválido"},
        parametros=[_P_REPUESTO], descripcion_404="Repuesto inexistente."),
    _Op("/api/inventario/alertas", "get", "Inventario", "alertas_stock",
        "Repuestos con stock bajo su umbral efectivo",
        "Los que más faltan primero. Mecánico o Administrador.",
        "200", _ref("PaginaAlertas"),
        {"umbral_general": 5, "total": 1, "alertas": [{
            "repuesto_id": 14, "nombre": "Filtro de aceite", "proveedor_nombre": "Repuestos del Sur",
            "stock": 2, "umbral_efectivo": 5, "faltan": 3}]},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido"}),
    _Op("/api/inventario/umbral-general", "get", "Inventario", "ver_umbral_general",
        "Umbral general vigente", "`umbral_general: null` si aún no se configura.",
        "200", _ref("UmbralGeneralSalida"),
        {"umbral_general": 5, "vigente_desde": _FECHA, "actualizado_por_id": 1},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido"}),
    _Op("/api/inventario/umbral-general", "put", "Inventario", "cambiar_umbral_general",
        "Configurar el umbral general", "Solo Administrador. El cambio queda en el historial.",
        "200", _ref("UmbralGeneralSalida"),
        {"umbral_general": 6, "vigente_desde": _FECHA_2, "actualizado_por_id": 1},
        {"401": "JWT ausente o inválido", "403": "Solo Administrador", "422": "Valor inválido"},
        cuerpo="UmbralGeneralEntrada",
        ejemplo_cuerpo={"umbral_general": 6, "observacion": "Temporada alta"}),
    _Op("/api/inventario/historial-umbral", "get", "Inventario", "historial_umbral",
        "Cambios de umbral (general y/o de un repuesto)", "Más recientes primero.",
        "200", {"type": "array", "items": _ref("CambioUmbral")},
        [{"historial_id": 4, "repuesto_id": None, "valor_anterior": 5, "valor_nuevo": 6,
          "administrador_id": 1, "fecha_hora": _FECHA_2, "observacion": "Temporada alta"}],
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Parámetros inválidos"},
        parametros=[
            _query("repuesto_id", "Solo los cambios del repuesto.", _ENTERO_OPCIONAL),
            _query("solo_general", "Solo los cambios del umbral general.",
                   {"type": "boolean", "default": False}),
            _LIMITE,
        ],
        descripcion_404="Repuesto inexistente."),
    _Op("/api/inventario/disponibilidad", "post", "Inventario", "validar_disponibilidad",
        "Validar si alcanza el stock antes de usar repuestos",
        "No mueve stock: responde si cada repuesto alcanza y cuántas unidades faltan. Con "
        "`orden_id` cuenta como disponible lo que esa orden ya reservó.",
        "200", _ref("ResultadoDisponibilidad"), _DISPONIBILIDAD,
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Datos inválidos"},
        cuerpo="ConsultaDisponibilidad",
        ejemplo_cuerpo={"orden_id": 31, "items": [{"repuesto_id": 12, "cantidad": 4}]},
        descripcion_404="Algún repuesto no existe."),
    _Op("/api/inventario/ordenes/{orden_id}/disponibilidad", "get", "Inventario",
        "disponibilidad_orden", "Validar el stock para lo que falta usar en una orden",
        "Requerido = repuestos de la versión aprobada vigente − lo ya consumido por la orden. "
        "Sirve para saber si una orden en 'Esperando repuestos' ya puede continuar.",
        "200", _ref("ResultadoDisponibilidad"),
        {**_DISPONIBILIDAD, "presupuesto_id": 7, "version": 1},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido",
         "409": "La orden no tiene un presupuesto aprobado", "422": "Identificador inválido"},
        con_orden_id=True, descripcion_404="La orden no tiene presupuesto."),
    _Op("/api/inventario/ordenes/{orden_id}/reserva", "post", "Inventario", "reservar_orden",
        "Reservar lo que falta usar del presupuesto aprobado (todo o nada)",
        "Ajusta la reserva de la orden a lo pendiente de su presupuesto aprobado. Si algún "
        "repuesto no alcanza no reserva nada y responde `reservado: false` con los faltantes.",
        "200", _ref("ResultadoReserva"),
        {"orden_id": 31, "reservado": True, "faltantes": [], "movimientos": [_MOVIMIENTO_COMPROMISO]},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido",
         "409": "La orden no tiene un presupuesto aprobado", "422": "Identificador inválido"},
        con_orden_id=True, descripcion_404="La orden no tiene presupuesto."),
    _Op("/api/inventario/ordenes/{orden_id}/consumos", "post", "Inventario", "consumir_orden",
        "Descontar varios repuestos usados en la orden (todo o nada)",
        "Usa primero lo reservado por la orden; nunca toma lo reservado por otra. Reenviar la "
        "misma `clave_operacion` devuelve lo ya aplicado con 200 y `repetido: true`.",
        "201", _ref("ResultadoOperacionOrden"),
        {"orden_id": 31, "movimientos": [_MOVIMIENTO_CONSUMO], "repetido": False},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Datos inválidos"},
        con_orden_id=True, cuerpo="ConsumoOrden",
        ejemplo_cuerpo={"clave_operacion": "consumo-orden-31-0001",
                        "items": [{"repuesto_id": 12, "cantidad": 2}]},
        descripcion_404="Algún repuesto no existe.",
        extra_respuestas={
            "200": _respuesta("Clave repetida: no se descontó de nuevo.",
                              _ref("ResultadoOperacionOrden")),
            "409": _respuesta("Stock insuficiente: `faltantes` por repuesto; no se aplicó nada.",
                              _ref("RechazoStock")),
        }),
    _Op("/api/inventario/ordenes/{orden_id}/liberacion", "post", "Inventario", "liberar_orden",
        "Liberar todo lo reservado por la orden",
        "Por ejemplo, al cancelarla. Idempotente por `clave_operacion`.",
        "200", _ref("ResultadoOperacionOrden"),
        {"orden_id": 31, "movimientos": [{**_MOVIMIENTO_COMPROMISO, "movimiento_id": 104,
                                          "tipo": "liberacion",
                                          "clave_operacion": "liberacion-orden-31"}],
         "repetido": False},
        {"401": "JWT ausente o inválido", "403": "Rol no permitido", "422": "Datos inválidos"},
        con_orden_id=True, cuerpo="LiberacionOrden",
        ejemplo_cuerpo={"clave_operacion": "liberacion-orden-31"}),
)


def _construir(op: _Op, error_404: dict[str, Any]) -> dict[str, Any]:
    respuestas_ok: dict[str, dict[str, Any]]
    if op.respuesta is None:
        respuestas_ok = {op.exito: {"description": op.resumen + "."}}
    else:
        respuestas_ok = {op.exito: _respuesta(op.resumen + ".", op.respuesta)}
        respuestas_ok[op.exito]["content"][_JSON]["examples"] = {"ejemplo": _ejemplo(op.ejemplo)}
    operacion = _operacion(
        tag=op.tag,
        resumen=op.resumen,
        descripcion=op.descripcion,
        operation_id=op.operation_id,
        cuerpo=op.cuerpo,
        respuestas_ok=respuestas_ok,
        errores_ms=op.errores,
        requiere_auth=True,
        con_orden_id=op.con_orden_id,
        parametros_extra=list(op.parametros),
        descripcion_404=op.descripcion_404,
        esquema_404=error_404,
    )
    if op.cuerpo is not None:
        cuerpo = operacion["requestBody"]
        cuerpo["required"] = not op.cuerpo_opcional
        cuerpo["content"][_JSON]["examples"] = {"ejemplo": _ejemplo(op.ejemplo_cuerpo)}
    for codigo, respuesta in op.extra_respuestas.items():
        operacion["responses"][codigo] = deepcopy(respuesta)
    if op.esquema_503 is not None:
        operacion["responses"]["503"] = _respuesta(
            _MS2_NO_DISPONIBLE + " o coordinación pendiente (MS3 responde "
            "`{\"detail\": ...}`); o pool de la Gateway agotado (GATEWAY_SATURADA).",
            {"oneOf": [_ref(op.esquema_503), _ref("ErrorRespuesta")]}
            if op.esquema_503 != "ErrorDetalle"
            else {"oneOf": [_ref("ErrorDetalle"), _ref("ErrorRespuesta")]},
        )
    return operacion


def caminos_ms3() -> dict[str, dict[str, Any]]:
    """Caminos `/api/*` de MS3 listos para `esquema["paths"]`."""
    error_404: dict[str, Any] = {"oneOf": [_ref("ErrorRespuesta"), _ref("ErrorDetalle")]}
    caminos: dict[str, dict[str, Any]] = {}
    for op in _OPERACIONES:
        caminos.setdefault(op.ruta, {})[op.metodo] = _construir(op, error_404)
    return caminos
