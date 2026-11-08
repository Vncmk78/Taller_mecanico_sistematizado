"""Diferencias entre el contrato publicado y el consumo real (Semana 8).

Compara el contrato OpenAPI congelado (`docs/openapi/sgtm-gateway-<versión>.json`)
con dos fuentes de «consumo real»:

1. **Lo que el frontend web lee y envía** (`gateway/contratos/consumo_web.py`,
   levantado de `frontend/src/infrastructure/api/*Service.ts`). Por cada llamada:
   la operación y el estado existen, cada campo que el cliente lee está publicado
   con un tipo compatible, lo que el cliente asume siempre presente es
   obligatorio, lo que puede ser `null` el cliente lo maneja, los enums coinciden
   y el body que arma el cliente es aceptado.
2. **Lo que la Gateway responde de verdad**: la Gateway real con MS1 y MS2 reales
   in-process (fixture `ecosistema` de `test_integracion_prefijos.py`) recorre
   las llamadas del cliente y del mecánico; cada respuesta, éxito o error, se
   valida contra el esquema publicado para su estado, y se buscan campos reales
   que el contrato no publica.

Las diferencias registradas en `docs/diferencias-contrato-consumo-real.md`
quedan como `xfail` estricto con su ID: al corregirlas la prueba pasa a XPASS y
obliga a retirar la marca.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from sqlalchemy import select

from gateway.contratos.consumo_web import CONSUMO_WEB, ConsumoWeb
from gateway.main import app as gateway_app
from services.ms1_auth.models import Rol
from services.ms1_auth.models.rol import UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from services.ms1_auth.security.passwords import hash_contrasena
from services.ms2_taller.integracion_ms3 import obtener_verificador_aprobacion_inicial
from services.ms2_taller.main import app as app_ms2
from services.ms2_taller.models import OrdenTrabajo
from services.ms2_taller.models.estado_orden import EN_REPARACION
from shared.auth import NombreRol
from shared.contratos_decisiones import AprobacionInicialOrdenVerificada

from test_integracion_prefijos import (  # noqa: F401  (ecosistema es fixture)
    ADMINISTRADOR,
    CLIENTE,
    DATOS_VEHICULO,
    autorizacion,
    crear_administrador,
    ecosistema,
)

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
_JSON = "application/json"

# Diferencias abiertas del consumo web: clave de ConsumoWeb -> ID del documento.
_DIFERENCIAS_WEB: dict[str, str] = {
    # D-01 se corrigió en el frontend (SCRUM-706), D-02 en el contrato 2.0.1 y
    # D-03 en el frontend. Una diferencia nueva se registra aquí con un ID nuevo.
    # D-04 se corrigió en el contrato 2.2.1.
}

# Diferencias abiertas de las respuestas vivas: (MÉTODO ruta estado) -> ID.
_DIFERENCIAS_VIVAS: dict[str, str] = {}


# ── contrato publicado ──────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def contrato() -> dict:
    version = gateway_app.version
    archivo = RAIZ_BACKEND / "docs" / "openapi" / f"sgtm-gateway-{version}.json"
    return json.loads(archivo.read_text(encoding="utf-8"))


def _resolver(contrato: dict, nodo: Any) -> Any:
    while isinstance(nodo, dict) and "$ref" in nodo:
        destino: Any = contrato
        for parte in nodo["$ref"][2:].split("/"):
            destino = destino[parte]
        nodo = {**destino, **{k: v for k, v in nodo.items() if k != "$ref"}}
    return nodo


def _normalizar(contrato: dict, esquema: Any) -> tuple[set[str], bool, dict, list | None]:
    """(tipos sin null, admite null, esquema sin la rama null, enum)."""
    esquema = _resolver(contrato, esquema or {})
    if "allOf" in esquema and len(esquema["allOf"]) == 1:
        resto = {k: v for k, v in esquema.items() if k != "allOf"}
        esquema = {**_resolver(contrato, esquema["allOf"][0]), **resto}
    alternativas = esquema.get("anyOf") or esquema.get("oneOf")
    if alternativas:
        ramas = [_resolver(contrato, a) for a in alternativas]
        no_nulas = [r for r in ramas if r.get("type") != "null"]
        tipos: set[str] = set()
        enum = None
        for rama in no_nulas:
            t, _, _, e = _normalizar(contrato, rama)
            tipos |= t
            enum = e or enum
        interno = no_nulas[0] if len(no_nulas) == 1 else {"anyOf": no_nulas}
        return tipos, len(no_nulas) < len(ramas), interno, enum
    tipo = esquema.get("type")
    tipos = set(tipo) if isinstance(tipo, list) else ({tipo} if tipo else set())
    admite_null = "null" in tipos
    tipos.discard("null")
    if "enum" in esquema and not tipos:
        tipos = {"string"}
    return tipos, admite_null, esquema, esquema.get("enum")


def _leer_declaracion(spec: Any) -> tuple[bool, bool, set[str], set | None, Any]:
    """(opcional, admite null, tipos, enum, anidado) de un campo declarado."""
    if isinstance(spec, str):
        opcional = spec.startswith("~")
        spec = spec.lstrip("~")
        nulo = spec.startswith("?")
        tipos = set(spec.lstrip("?").split("|"))
        if "number" in tipos:
            tipos.add("integer")
        return opcional, nulo, tipos, None, None
    if isinstance(spec, tuple) and spec and spec[0] == "?":
        return False, True, {"object"}, None, spec[1]
    if isinstance(spec, tuple):
        return False, False, {"string"}, set(spec), None
    if isinstance(spec, list):
        return False, False, {"array"}, None, spec[0]
    return False, False, {"object"}, None, spec


def _comparar_respuesta(contrato: dict, declarado: Any, esquema: Any, ruta: str) -> list[str]:
    tipos, _, esquema, _ = _normalizar(contrato, esquema)
    if isinstance(declarado, str):
        if tipos and not tipos <= set(declarado.split("|")):
            return [f"{ruta}: el contrato publica {sorted(tipos)} y el cliente lee {declarado}"]
        return []
    if isinstance(declarado, list):
        if "array" not in tipos:
            return [f"{ruta}: el cliente espera una lista y el contrato publica {sorted(tipos)}"]
        return _comparar_respuesta(contrato, declarado[0], esquema.get("items"), f"{ruta}[]")

    diferencias: list[str] = []
    propiedades = esquema.get("properties", {})
    obligatorios = set(esquema.get("required", []))
    for campo, spec in declarado.items():
        nombre = f"{ruta}.{campo}" if ruta else campo
        opcional, nulo, tipos_cliente, enum_cliente, anidado = _leer_declaracion(spec)
        if campo not in propiedades:
            diferencias.append(f"{nombre}: el cliente lo lee y el contrato no lo publica")
            continue
        tipos_c, nulo_c, interno, enum_c = _normalizar(contrato, propiedades[campo])
        if campo not in obligatorios and not opcional:
            diferencias.append(
                f"{nombre}: el cliente lo asume siempre presente y el contrato no lo exige"
            )
        if nulo_c and not nulo:
            diferencias.append(f"{nombre}: el contrato admite null y el cliente no lo maneja")
        if tipos_c and not tipos_c <= tipos_cliente:
            diferencias.append(
                f"{nombre}: el contrato publica {sorted(tipos_c)} y el cliente lee "
                f"{sorted(tipos_cliente)}"
            )
        if enum_cliente is not None:
            if enum_c is None:
                diferencias.append(f"{nombre}: el cliente espera un enum y el contrato no lo fija")
            elif set(enum_c) != enum_cliente:
                diferencias.append(
                    f"{nombre}: enum del contrato {sorted(enum_c)} y del cliente "
                    f"{sorted(enum_cliente)}"
                )
        if anidado is not None:
            if "array" in tipos_cliente:
                diferencias += _comparar_respuesta(
                    contrato, [anidado], propiedades[campo], nombre
                )
            else:
                diferencias += _comparar_respuesta(contrato, anidado, interno, nombre)
    return diferencias


def _comparar_cuerpo(contrato: dict, declarado: dict, operacion: dict) -> list[str]:
    contenido = operacion.get("requestBody", {}).get("content", {})
    if not contenido:
        return ["body: el cliente envía un body y el contrato no declara ninguno"]
    _, media = next(iter(contenido.items()))
    _, _, esquema, _ = _normalizar(contrato, media["schema"])
    propiedades = esquema.get("properties", {})
    diferencias = []
    for campo, spec in declarado.items():
        _, nulo, _, enum_cliente, _ = _leer_declaracion(spec)
        if campo not in propiedades:
            diferencias.append(f"body.{campo}: el cliente lo envía y el contrato no lo acepta")
            continue
        _, nulo_c, _, enum_c = _normalizar(contrato, propiedades[campo])
        if nulo and not nulo_c:
            diferencias.append(f"body.{campo}: el cliente puede enviar null y el contrato no")
        if enum_cliente and enum_c and enum_cliente - set(enum_c):
            diferencias.append(
                f"body.{campo}: el cliente envía {sorted(enum_cliente - set(enum_c))}"
            )
    faltan = set(esquema.get("required", [])) - set(declarado)
    if faltan:
        diferencias.append(f"body: obligatorios que el cliente no envía {sorted(faltan)}")
    return diferencias


def diferencias_consumo(contrato: dict, consumo: ConsumoWeb) -> list[str]:
    operacion = contrato["paths"].get(consumo.ruta, {}).get(consumo.metodo)
    if operacion is None:
        return ["la operación no está publicada"]
    diferencias = []
    if consumo.cuerpo is not None:
        diferencias += _comparar_cuerpo(contrato, consumo.cuerpo, operacion)
    respuesta = operacion["responses"].get(consumo.estado)
    if respuesta is None:
        return diferencias + [f"el estado {consumo.estado} no está publicado"]
    esquema = respuesta.get("content", {}).get(_JSON, {}).get("schema")
    return diferencias + _comparar_respuesta(contrato, consumo.respuesta, esquema, "")


# ── 1. consumo declarado por el frontend web ───────────────────────────────


def _casos_web():
    for consumo in CONSUMO_WEB:
        marcas = []
        if consumo.clave in _DIFERENCIAS_WEB:
            marcas.append(pytest.mark.xfail(reason=_DIFERENCIAS_WEB[consumo.clave], strict=True))
        yield pytest.param(consumo, id=consumo.clave, marks=marcas)


@pytest.mark.parametrize("consumo", _casos_web())
def test_consumo_web_coincide_con_contrato_publicado(consumo: ConsumoWeb, contrato) -> None:
    diferencias = diferencias_consumo(contrato, consumo)
    assert not diferencias, f"{consumo.clave}: {diferencias}"


def test_diferencias_web_registradas_existen_en_el_catalogo() -> None:
    claves = {consumo.clave for consumo in CONSUMO_WEB}
    assert set(_DIFERENCIAS_WEB) <= claves
    assert len(claves) == len(CONSUMO_WEB), "consumos duplicados"


# ── 2. respuestas reales de la Gateway contra el esquema publicado ──────────


class _SinAprobacionInicial:
    """MS3 simulado: la orden no tiene aprobación inicial (cancelable)."""

    def consultar(self, orden_id: int, _token: str) -> AprobacionInicialOrdenVerificada:
        return AprobacionInicialOrdenVerificada(orden_id=orden_id, aprobacion_registrada=False)


_MECANICO = ("mecanico@integracion.cl", "MecanicoIntegracion123!", "Mecánico Integración")


def _crear_mecanico(sesion_ms1, gw) -> str:
    rol = sesion_ms1.scalar(select(Rol).where(Rol.nombre == NombreRol.MECANICO.value))
    usuario = Usuario(
        correo=_MECANICO[0],
        nombre=_MECANICO[2],
        contrasena_hash=hash_contrasena(_MECANICO[1]),
        activo=True,
    )
    sesion_ms1.add(usuario)
    sesion_ms1.flush()
    sesion_ms1.add(UsuarioRol(usuario=usuario, rol=rol))
    sesion_ms1.commit()
    login = gw.post("/api/auth/login", json={"email": _MECANICO[0], "password": _MECANICO[1]})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


@pytest.fixture
def respuestas_reales(ecosistema, mecanicos_validos) -> list[tuple[str, str, int, Any]]:  # noqa: F811
    """Recorre los flujos de cliente y mecánico; devuelve (método, ruta, estado, body)."""
    gw, sesion_ms1, sesion_ms2 = ecosistema
    app_ms2.dependency_overrides[obtener_verificador_aprobacion_inicial] = (
        lambda: _SinAprobacionInicial()
    )
    registro: list[tuple[str, str, int, Any]] = []

    def llamar(metodo: str, ruta: str, url: str, token: str | None = None, **kwargs):
        cabeceras = autorizacion(token) if token else {}
        respuesta = gw.request(metodo, url, headers=cabeceras, **kwargs)
        cuerpo = respuesta.json() if respuesta.content else None
        registro.append((metodo.lower(), ruta, respuesta.status_code, cuerpo))
        return respuesta

    try:
        email, clave, nombre = CLIENTE
        llamar("POST", "/api/auth/register", "/api/auth/register",
               json={"email": email, "password": clave, "full_name": nombre})
        llamar("POST", "/api/auth/login", "/api/auth/login",
               json={"email": email, "password": "incorrecta"})
        cliente = llamar("POST", "/api/auth/login", "/api/auth/login",
                         json={"email": email, "password": clave}).json()["access_token"]
        llamar("GET", "/api/auth/me", "/api/auth/me", cliente)
        # Sin perfil MS2 todavía: vehículos responde 404 y la consulta no lo crea.
        llamar("GET", "/api/vehiculos", "/api/vehiculos", cliente)
        llamar("GET", "/api/clientes/perfil", "/api/clientes/perfil", cliente)
        # La web prepara el perfil por la Gateway (antes se insertaba en la base).
        llamar("POST", "/api/clientes/perfil", "/api/clientes/perfil", cliente, json={})
        llamar("POST", "/api/clientes/perfil", "/api/clientes/perfil", cliente, json={})
        llamar("GET", "/api/clientes/perfil", "/api/clientes/perfil", cliente)

        llamar("POST", "/api/vehiculos", "/api/vehiculos", cliente, json={})
        vehiculo_id = llamar("POST", "/api/vehiculos", "/api/vehiculos", cliente,
                             json=DATOS_VEHICULO).json()["vehiculo_id"]
        llamar("GET", "/api/vehiculos", "/api/vehiculos", cliente)
        llamar("GET", "/api/vehiculos/{vehiculo_id}", f"/api/vehiculos/{vehiculo_id}", cliente)
        llamar("GET", "/api/vehiculos/{vehiculo_id}", "/api/vehiculos/9999", cliente)

        administrador = crear_administrador(sesion_ms1, gw, *ADMINISTRADOR)
        mecanico = _crear_mecanico(sesion_ms1, gw)
        mecanico_id = gw.get("/api/auth/me", headers=autorizacion(mecanico)).json()["id"]
        # El Administrador configura los límites desde la web (antes la
        # capacidad se insertaba directamente en la base de MS2).
        cupo = "/api/ordenes/configuracion/capacidad/ingresos-diarios"
        capacidad = "/api/ordenes/configuracion/capacidad/mecanicos"
        llamar("GET", cupo, cupo, administrador)
        llamar("PUT", cupo, cupo, administrador, json={"max_ingresos_diarios": 50})
        llamar("GET", capacidad, capacidad, administrador)
        llamar("PUT", capacidad, capacidad, administrador, json={"max_ordenes_activas": 5})
        llamar("PUT", capacidad, capacidad, administrador, json={"max_ordenes_activas": 0})
        orden_id = llamar("POST", "/api/ordenes", "/api/ordenes", administrador,
                          json={"vehiculo_id": vehiculo_id}).json()["orden_id"]
        base = f"/api/ordenes/{orden_id}"
        llamar("PUT", "/api/ordenes/{orden_id}/mecanico", f"{base}/mecanico", administrador,
               json={"mecanico_id": mecanico_id})
        # Se conserva el rechazo de capacidad y luego se prepara la asignación
        # válida: la atención debe terminar antes de abrir otra del vehículo.
        llamar("PUT", capacidad, capacidad, administrador, json={"max_ordenes_activas": 5})
        asignacion = llamar("PUT", "/api/ordenes/{orden_id}/mecanico", f"{base}/mecanico",
                            administrador, json={"mecanico_id": mecanico_id})
        assert asignacion.status_code == 200
        duplicada = llamar("POST", "/api/ordenes", "/api/ordenes", administrador,
                           json={"vehiculo_id": vehiculo_id})
        assert duplicada.status_code == 409

        llamar("GET", "/api/ordenes", "/api/ordenes")
        llamar("GET", "/api/ordenes", "/api/ordenes", cliente)
        llamar("GET", "/api/ordenes/{orden_id}", base, cliente)
        llamar("GET", "/api/ordenes/{orden_id}/historial", f"{base}/historial", cliente)
        llamar("GET", "/api/vehiculos", "/api/vehiculos", mecanico)
        llamar("GET", "/api/vehiculos/asignados", "/api/vehiculos/asignados", mecanico)
        llamar("GET", "/api/vehiculos/{vehiculo_id}", f"/api/vehiculos/{vehiculo_id}", mecanico)
        llamar("POST", "/api/ordenes/{orden_id}/bitacora", f"{base}/bitacora", mecanico,
               json={"tipo": "accion", "descripcion": "Cambio de pastillas",
                     "repuestos": [{"nombre": "Pastillas de freno", "cantidad": 2}]})
        llamar("POST", "/api/ordenes/{orden_id}/bitacora", f"{base}/bitacora", mecanico,
               json={"tipo": "observacion", "descripcion": "x",
                     "repuestos": [{"nombre": "Pastillas", "cantidad": 1}]})
        llamar("GET", "/api/ordenes/{orden_id}/bitacora", f"{base}/bitacora", cliente)

        orden = sesion_ms2.get(OrdenTrabajo, orden_id)
        orden.estado_codigo = EN_REPARACION
        sesion_ms2.commit()
        llamar("PATCH", "/api/ordenes/{orden_id}/estado", f"{base}/estado", cliente,
               json={"estado_destino": 6})
        llamar("PATCH", "/api/ordenes/{orden_id}/estado", f"{base}/estado", mecanico,
               json={"estado_destino": 6})
        entregada = llamar("POST", "/api/ordenes/{orden_id}/entrega", f"{base}/entrega",
                           administrador, json={})
        assert entregada.status_code == 200

        # Segunda orden del mismo vehículo: solicitud y confirmación de cancelación.
        segunda = llamar("POST", "/api/ordenes", "/api/ordenes", administrador,
                         json={"vehiculo_id": vehiculo_id}).json()["orden_id"]
        base = f"/api/ordenes/{segunda}"
        motivo = {"motivo": "El cliente no continuará"}
        llamar("POST", "/api/ordenes/{orden_id}/cancelacion", f"{base}/cancelacion",
               cliente, json=motivo)
        llamar("POST", "/api/ordenes/{orden_id}/cancelacion", f"{base}/cancelacion",
               cliente, json=motivo)
        llamar("POST", "/api/ordenes/{orden_id}/cancelacion/confirmacion",
               f"{base}/cancelacion/confirmacion", administrador)
        devolucion = "/api/ordenes/{orden_id}/devolucion"
        llamar("POST", devolucion, f"{base}/devolucion", cliente, json={})
        primera = llamar("POST", devolucion, f"{base}/devolucion", administrador, json={})
        segunda_devolucion = llamar("POST", devolucion, f"{base}/devolucion", administrador, json={})
        assert primera.status_code == segunda_devolucion.status_code == 200
        assert primera.json() == segunda_devolucion.json()
        assert primera.json()["estado_codigo"] == 8
        ruta_solicitar = "/api/ordenes/{orden_id}/nueva-atencion"
        solicitud = llamar("POST", ruta_solicitar, f"{base}/nueva-atencion", cliente,
                           json={"descripcion": "Revisar nuevamente los frenos"})
        assert solicitud.status_code == 201
        repetida = llamar("POST", ruta_solicitar, f"{base}/nueva-atencion", cliente,
                          json={"descripcion": "Revisar nuevamente los frenos"})
        assert repetida.status_code == 200 and repetida.json() == solicitud.json()
        llamar("POST", ruta_solicitar, f"{base}/nueva-atencion", cliente,
               json={"descripcion": "Otra descripción"})
        ruta_lista = "/api/ordenes/nuevas-atenciones"
        llamar("GET", ruta_lista, ruta_lista, cliente, params={"orden_cancelada_id": segunda})
        llamar("GET", ruta_lista, ruta_lista, administrador)
        llamar("GET", ruta_lista, ruta_lista, mecanico)
        llamar("GET", "/api/ordenes/nuevas-atenciones/{solicitud_id}",
               f"{ruta_lista}/{solicitud.json()['solicitud_id']}", cliente)
        llamar("GET", "/api/ordenes/vehiculo/{vehiculo_id}/historial",
               f"/api/ordenes/vehiculo/{vehiculo_id}/historial", cliente,
               params={"limit": 10, "offset": 0})
        return registro
    finally:
        app_ms2.dependency_overrides.pop(obtener_verificador_aprobacion_inicial, None)


def _campos_no_publicados(contrato: dict, cuerpo: Any, esquema: Any, ruta: str = "") -> list[str]:
    """Campos de la respuesta real que el esquema publicado no declara."""
    _, _, esquema, _ = _normalizar(contrato, esquema)
    if isinstance(cuerpo, list):
        extra: list[str] = []
        for elemento in cuerpo:
            extra += _campos_no_publicados(contrato, elemento, esquema.get("items"), f"{ruta}[]")
        return sorted(set(extra))
    if not isinstance(cuerpo, dict) or "properties" not in esquema:
        return []
    extra = []
    for campo, valor in cuerpo.items():
        nombre = f"{ruta}.{campo}" if ruta else campo
        if campo not in esquema["properties"]:
            extra.append(nombre)
        else:
            extra += _campos_no_publicados(contrato, valor, esquema["properties"][campo], nombre)
    return extra


def diferencias_respuesta(contrato: dict, metodo: str, ruta: str, estado: int, cuerpo) -> list[str]:
    operacion = contrato["paths"][ruta][metodo]
    respuesta = operacion["responses"].get(str(estado))
    if respuesta is None:
        return [f"el estado {estado} no está publicado"]
    esquema = respuesta.get("content", {}).get(_JSON, {}).get("schema")
    if esquema is None:
        return [] if cuerpo is None else ["responde un body que el contrato no declara"]
    validador = Draft202012Validator({**esquema, "components": contrato["components"]})
    diferencias = [
        f"{'/'.join(map(str, error.absolute_path)) or '(raíz)'}: {error.message[:160]}"
        for error in validador.iter_errors(cuerpo)
    ]
    diferencias += [
        f"{campo}: viene en la respuesta y el contrato no lo publica"
        for campo in _campos_no_publicados(contrato, cuerpo, esquema)
    ]
    return diferencias


def test_respuestas_reales_cumplen_el_contrato_publicado(contrato, respuestas_reales) -> None:
    encontradas: dict[str, list[str]] = {}
    for metodo, ruta, estado, cuerpo in respuestas_reales:
        diferencias = diferencias_respuesta(contrato, metodo, ruta, estado, cuerpo)
        if diferencias:
            encontradas[f"{metodo.upper()} {ruta} {estado}"] = diferencias
    nuevas = {k: v for k, v in encontradas.items() if k not in _DIFERENCIAS_VIVAS}
    corregidas = set(_DIFERENCIAS_VIVAS) - set(encontradas)
    assert not nuevas, f"Diferencias nuevas entre respuestas reales y contrato: {nuevas}"
    assert not corregidas, f"Ya no ocurren, retirar de _DIFERENCIAS_VIVAS: {corregidas}"


def test_el_recorrido_cubre_exitos_y_errores_del_consumo(respuestas_reales) -> None:
    """El recorrido vivo ejercita todas las operaciones de MS1/MS2 del frontend."""
    cubiertas = {(m, r) for m, r, _, _ in respuestas_reales}
    estados = {(m, r, e) for m, r, e, _ in respuestas_reales}
    esperadas = {
        (c.metodo, c.ruta)
        for c in CONSUMO_WEB
        if c.ruta.startswith((
            "/api/auth/login", "/api/auth/register", "/api/auth/me", "/api/clientes",
            "/api/vehiculos", "/api/ordenes",
        ))
    }
    assert esperadas <= cubiertas, sorted(esperadas - cubiertas)
    for esperado in [
        ("post", "/api/auth/login", 401),
        ("put", "/api/ordenes/configuracion/capacidad/mecanicos", 200),
        ("put", "/api/ordenes/configuracion/capacidad/mecanicos", 422),
        ("put", "/api/ordenes/configuracion/capacidad/ingresos-diarios", 200),
        ("post", "/api/ordenes", 201),
        ("post", "/api/ordenes/{orden_id}/nueva-atencion", 201),
        ("post", "/api/ordenes/{orden_id}/nueva-atencion", 200),
        ("post", "/api/ordenes/{orden_id}/nueva-atencion", 409),
        ("get", "/api/ordenes/nuevas-atenciones", 403),
        ("post", "/api/auth/register", 201),
        ("get", "/api/vehiculos", 404),
        ("get", "/api/clientes/perfil", 404),
        ("post", "/api/clientes/perfil", 201),
        ("post", "/api/clientes/perfil", 200),
        ("get", "/api/clientes/perfil", 200),
        ("post", "/api/vehiculos", 422),
        ("get", "/api/vehiculos/{vehiculo_id}", 404),
        ("get", "/api/vehiculos", 403),
        ("get", "/api/ordenes", 401),
        ("post", "/api/ordenes/{orden_id}/bitacora", 422),
        ("post", "/api/ordenes/{orden_id}/cancelacion", 201),
        ("post", "/api/ordenes/{orden_id}/cancelacion", 200),
        ("patch", "/api/ordenes/{orden_id}/estado", 403),
        ("post", "/api/ordenes/{orden_id}/cancelacion/confirmacion", 200),
    ]:
        assert esperado in estados, esperado


def test_d01_la_cancelacion_real_no_trae_los_campos_de_orden(respuestas_reales) -> None:
    """D-01: la respuesta es una solicitud, no una orden (el frontend ya no la lee)."""
    (cuerpo,) = [
        c for m, r, e, c in respuestas_reales
        if (m, r, e) == ("post", "/api/ordenes/{orden_id}/cancelacion", 201)
    ]
    assert cuerpo["estado"] == "pendiente"
    assert "solicitud_id" in cuerpo
    assert "estado_codigo" not in cuerpo and "vehiculo_id" not in cuerpo
