"""Consumo real del frontend web contra la Gateway (Semana 8).

Declaración, del lado del consumidor, de **qué llama el frontend web y qué
campos lee** de cada respuesta. Se levantó leyendo `frontend/src/infrastructure/
api/*Service.ts` (las interfaces `*Api` y los cuerpos que arman los servicios).
Es la «Fase 0» de `docs/estudio-pruebas-contrato-consumidores.md`: el
consumidor declara lo que usa y el backend lo compara con el contrato publicado
(`tests/test_contrato_consumo_real.py`).

Formato de cada campo (`cuerpo` y `respuesta`):

* `"string"`, `"integer"`, `"boolean"`, `"number"`, `"object"`; varios tipos
  aceptados se separan con `|` (`"string|number"`).
* Prefijo `?`: el cliente maneja `null` (`"?integer"` ↔ `number | null`).
* Prefijo `~`: el cliente tolera que el campo no venga (`campo?:` en TS) o,
  en un cuerpo, que lo omite a veces.
* Tupla de strings: enum que el cliente contempla (`("usuario", "sistema")`).
* `dict`: objeto anidado; `[x]`: lista de `x`; `("?", dict)`: objeto o `null`.

Si un servicio del frontend cambia lo que lee o envía, se actualiza aquí en el
mismo cambio. Lo que no aparece aquí, el frontend no lo usa.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

Campos = dict[str, Any]


@dataclass(frozen=True)
class ConsumoWeb:
    """Una llamada HTTP del frontend y lo que espera de la respuesta."""

    servicio: str
    metodo: str
    ruta: str
    estado: str
    respuesta: Campos | list
    cuerpo: Campos | None = None

    @property
    def clave(self) -> str:
        return f"{self.servicio} {self.metodo.upper()} {self.ruta}"


# ── formas que lee el frontend (interfaces *Api de los servicios) ──────────

PERFIL_CLIENTE: Campos = {  # PerfilClienteService.ts → PerfilClienteApi
    "cliente_id": "integer",
    "usuario_id": "integer",
    "telefono": "?string",
}

USUARIO: Campos = {  # AuthService.ts → ApiUser
    "id": "integer",
    "email": "string",
    "full_name": "string",
    "roles": ["string"],
    "is_active": "boolean",
}
VEHICULO: Campos = {  # VehicleService.ts → VehiculoApi
    "vehiculo_id": "integer",
    "cliente_id": "integer",
    "patente": "string",
    "marca": "string",
    "modelo": "string",
    "anio": "?integer",
    "kilometraje": "?integer",
}
ORDEN: Campos = {  # OrderService.ts → OrdenRespuesta
    "orden_id": "integer",
    "vehiculo_id": "integer",
    "ingreso_id": "integer",
    "estado_codigo": "integer",
    "mecanico_actual_id": "?integer",
    "creado_por_id": "integer",
    "creado_en": "string",
    "actualizado_en": "string",
    "devuelto_en": "?string",
    "devuelto_por_id": "?integer",
}
CUPO_DIARIO: Campos = {  # ConfiguracionTallerService.ts → CupoDiarioApi
    "max_ingresos_diarios": "?integer",
    "actualizado_por_id": "?integer",
    "actualizado_en": "string",
    "jornada_local": "string",
    "ingresos_registrados": "integer",
    "sobre_limite": "boolean",
}

CAPACIDAD_MECANICOS: Campos = {  # ConfiguracionTallerService.ts → CapacidadMecanicosApi
    "max_ordenes_activas": "?integer",
    "actualizado_por_id": "?integer",
    "actualizado_en": "string",
    "mecanicos_sobre_limite": [{"mecanico_id": "integer", "ordenes_activas": "integer"}],
}

HISTORIAL: Campos = {  # OrderService.ts → HistorialEstadoApi
    "historial_id": "integer",
    "orden_id": "integer",
    "estado_anterior": "?integer",
    "estado_nuevo": "integer",
    "actor_usuario_id": "?integer",
    "origen": ("usuario", "sistema"),
    "fecha_hora": "string",
    "observacion": "~?string",
}
REPUESTO_BITACORA: Campos = {"nombre": "string", "cantidad": "integer"}
BITACORA: Campos = {  # OrderService.ts → BitacoraApi
    "bitacora_id": "integer",
    "orden_id": "integer",
    "autor_usuario_id": "integer",
    "tipo": ("observacion", "accion"),
    "descripcion": "string",
    "creado_en": "string",
    "repuestos": [REPUESTO_BITACORA],
}
EVIDENCIA: Campos = {  # EvidenciaService.ts → EvidenciaApi
    "evidencia_id": "string",
    "orden_id": "integer",
    "presupuesto_id": "?integer",
    "contexto": "string",
    "tipo_archivo": "string",
    "visible_cliente": "boolean",
    "estado": "string",
    "nombre_original": "string",
    "content_type": "string",
    "tamano_bytes": "integer",
    "creada_en": "string",
}
_ESTADOS_VERSION = ("borrador", "enviada", "aprobada", "rechazada")
ITEM_PRESUPUESTO: Campos = {  # PresupuestoService.ts → ItemSalidaApi
    "item_id": "integer",
    "tipo": ("repuesto", "mano_de_obra"),
    "descripcion": "string",
    "cantidad": "string|number",
    "precio_unitario": "string|number",
    "subtotal": "string|number",
    "repuesto_id": "?integer",
    "repuesto_nombre": "~?string",
    "proveedor_nombre": "~?string",
}
DECISION: Campos = {  # PresupuestoService.ts → DecisionSalidaApi
    "decision_id": "integer",
    "decision": ("aprobado", "rechazado"),
    "cliente_usuario_id": "integer",
    "fecha_hora": "string",
    "motivo": "?string",
}
VERSION: Campos = {  # PresupuestoService.ts → VersionDetalleApi
    "numero": "integer",
    "estado": _ESTADOS_VERSION,
    "es_modificacion": "boolean",
    "creado_por_id": "integer",
    "creado_en": "string",
    "enviado_en": "?string",
    "bloqueada_en": "?string",
    "total": "string|number",
    "items": [ITEM_PRESUPUESTO],
    "decision": ("?", DECISION),
}
RESUMEN_PRESUPUESTO: Campos = {  # PresupuestoService.ts → PresupuestoResumenApi
    "presupuesto_id": "integer",
    "orden_id": "integer",
    "creado_en": "string",
    "cantidad_versiones": "integer",
    "ultima_version": "integer",
    "estado_ultima_version": _ESTADOS_VERSION,
    "total_ultima_version": "string|number",
    "version_vigente": "?integer",
}
DETALLE_PRESUPUESTO: Campos = {**RESUMEN_PRESUPUESTO, "versiones": [VERSION]}


CONSUMO_WEB: tuple[ConsumoWeb, ...] = (
    # ── AuthService ─────────────────────────────────────────────────────
    ConsumoWeb(
        "AuthService.login", "post", "/api/auth/login", "200",
        {"access_token": "string", "token_type": "string", "user": USUARIO},
        cuerpo={"email": "string", "password": "string"},
    ),
    ConsumoWeb(
        "AuthService.register", "post", "/api/auth/register", "201", USUARIO,
        cuerpo={"email": "string", "password": "string", "full_name": "string"},
    ),
    ConsumoWeb("AuthService.getProfile", "get", "/api/auth/me", "200", USUARIO),
    # ── PerfilClienteService ────────────────────────────────────────────
    # Tras el login de un Cliente (ClientProfileGate). Sin teléfono envía {}.
    ConsumoWeb(
        "PerfilClienteService.preparar", "post", "/api/clientes/perfil", "201",
        PERFIL_CLIENTE, cuerpo={"telefono": "~string"},
    ),
    ConsumoWeb(
        "PerfilClienteService.preparar (existente)", "post", "/api/clientes/perfil",
        "200", PERFIL_CLIENTE, cuerpo={"telefono": "~string"},
    ),
    ConsumoWeb("AuthService.listarUsuarios", "get", "/api/auth/usuarios", "200", [USUARIO]),
    # ── VehicleService ──────────────────────────────────────────────────
    ConsumoWeb(
        "VehicleService.getMyVehicles/getAllVehicles", "get", "/api/vehiculos", "200",
        [VEHICULO],
    ),
    ConsumoWeb(
        "VehicleService.getAssignedVehicles", "get", "/api/vehiculos/asignados", "200",
        [VEHICULO],
    ),
    ConsumoWeb(
        "VehicleService.getVehicleById", "get", "/api/vehiculos/{vehiculo_id}", "200",
        VEHICULO,
    ),
    ConsumoWeb(
        "VehicleService.createVehicle", "post", "/api/vehiculos", "201", VEHICULO,
        cuerpo={
            "patente": "string",
            "marca": "string",
            "modelo": "string",
            "anio": "?integer",
            "kilometraje": "?integer",
        },
    ),
    # ── OrderService ────────────────────────────────────────────────────
    ConsumoWeb("OrderService.getOrders", "get", "/api/ordenes", "200", [ORDEN]),
    ConsumoWeb(
        "OrderService.crearOrden", "post", "/api/ordenes", "201", ORDEN,
        cuerpo={"vehiculo_id": "integer"},
    ),
    # ── ConfiguracionTallerService (portal Administrador) ───────────────
    ConsumoWeb(
        "ConfiguracionTallerService.obtenerCupoDiario", "get",
        "/api/ordenes/configuracion/capacidad/ingresos-diarios", "200", CUPO_DIARIO,
    ),
    ConsumoWeb(
        "ConfiguracionTallerService.configurarCupoDiario", "put",
        "/api/ordenes/configuracion/capacidad/ingresos-diarios", "200", CUPO_DIARIO,
        cuerpo={"max_ingresos_diarios": "integer"},
    ),
    ConsumoWeb(
        "ConfiguracionTallerService.obtenerCapacidadMecanicos", "get",
        "/api/ordenes/configuracion/capacidad/mecanicos", "200", CAPACIDAD_MECANICOS,
    ),
    ConsumoWeb(
        "ConfiguracionTallerService.configurarCapacidadMecanicos", "put",
        "/api/ordenes/configuracion/capacidad/mecanicos", "200", CAPACIDAD_MECANICOS,
        cuerpo={"max_ordenes_activas": "integer"},
    ),
    ConsumoWeb("OrderService.getOrderById", "get", "/api/ordenes/{orden_id}", "200", ORDEN),
    ConsumoWeb(
        "OrderService.getOrderHistory", "get", "/api/ordenes/{orden_id}/historial", "200",
        [HISTORIAL],
    ),
    ConsumoWeb(
        "OrderService.getOrderBitacora", "get", "/api/ordenes/{orden_id}/bitacora", "200",
        [BITACORA],
    ),
    ConsumoWeb(
        "OrderService.registrarBitacora", "post", "/api/ordenes/{orden_id}/bitacora",
        "201", BITACORA,
        cuerpo={"tipo": ("observacion", "accion"), "descripcion": "string",
                "repuestos": [REPUESTO_BITACORA]},
    ),
    ConsumoWeb(
        "OrderService.cambiarEstado", "patch", "/api/ordenes/{orden_id}/estado", "200",
        ORDEN, cuerpo={"estado_destino": "integer", "observacion": "~string"},
    ),
    ConsumoWeb(
        "OrderService.asignarMecanico", "put", "/api/ordenes/{orden_id}/mecanico", "200",
        ORDEN, cuerpo={"mecanico_id": "integer", "observacion": "~string"},
    ),
    ConsumoWeb(
        "OrderService.registrarEntrega", "post", "/api/ordenes/{orden_id}/entrega", "200",
        ORDEN, cuerpo={"observacion": "~string"},
    ),
    ConsumoWeb(
        "OrderService.registrarDevolucion", "post", "/api/ordenes/{orden_id}/devolucion",
        "200", {**ORDEN, "devuelto_en": "string", "devuelto_por_id": "integer"},
        cuerpo={},
    ),
    # No lee la respuesta (es una solicitud pendiente, no una orden): después
    # vuelve a pedir la orden con getOrderById. Corregido en SCRUM-706 (D-01).
    ConsumoWeb(
        "OrderService.cancelarComoCliente", "post", "/api/ordenes/{orden_id}/cancelacion",
        "201", {}, cuerpo={"motivo": "string"},
    ),
    ConsumoWeb(
        "OrderService.confirmarCancelacion", "post",
        "/api/ordenes/{orden_id}/cancelacion/confirmacion", "200", ORDEN,
    ),
    ConsumoWeb(
        "OrderService.getVehicleOrderHistory", "get",
        "/api/ordenes/vehiculo/{vehiculo_id}/historial", "200",
        {"items": [ORDEN], "total": "integer", "limit": "integer", "offset": "integer"},
    ),
    # ── EvidenciaService ────────────────────────────────────────────────
    ConsumoWeb("EvidenciaService.getByOrder", "get", "/api/evidencias", "200", [EVIDENCIA]),
    ConsumoWeb(
        "EvidenciaService.getById", "get", "/api/evidencias/{evidencia_id}", "200",
        EVIDENCIA,
    ),
    ConsumoWeb(
        "EvidenciaService.getDownloadUrl", "get",
        "/api/evidencias/{evidencia_id}/descarga", "200",
        {"url": "string", "expira_en": "integer"},
    ),
    ConsumoWeb(
        "EvidenciaService.crear", "post", "/api/evidencias", "201", EVIDENCIA,
        cuerpo={
            "archivo": "string",
            "orden_id": "string|integer",
            "contexto": "string",
            "presupuesto_id": "~string|integer",
            "visible_cliente": "~string|boolean",
        },
    ),
    # ── PresupuestoService ──────────────────────────────────────────────
    ConsumoWeb(
        "PresupuestoService.getByOrder", "get", "/api/presupuestos", "200",
        {"total": "integer", "desde": "integer", "limite": "integer",
         "presupuestos": [RESUMEN_PRESUPUESTO]},
    ),
    ConsumoWeb(
        "PresupuestoService.getById", "get", "/api/presupuestos/{presupuesto_id}", "200",
        DETALLE_PRESUPUESTO,
    ),
    ConsumoWeb(
        "PresupuestoService.decidir", "post",
        "/api/presupuestos/{presupuesto_id}/versiones/{numero}/decision", "201",
        {"presupuesto": DETALLE_PRESUPUESTO, "efecto_en_orden": "?string",
         "decision_id": "?integer", "aplicacion_en_orden": "?object"},
        cuerpo={"decision": ("aprobado", "rechazado"), "motivo": "~string",
                "confirmar_cancelacion": "~boolean"},
    ),
)
