"""Pruebas de la documentación OpenAPI/Swagger de la Gateway.

Verifican que `/openapi.json` publica los 14 endpoints reales de Auth,
Vehículos y Órdenes con sus contratos y seguridad, que el proxy genérico no
aparece, y que las copias de `gateway/contratos` no se desactualizan respecto
a los esquemas reales de MS1 y MS2.
"""
from __future__ import annotations

import pytest
from fastapi.openapi.models import OpenAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from gateway.contratos import auth as contratos_auth
from gateway.contratos import ordenes as contratos_ordenes
from gateway.contratos import vehiculos as contratos_vehiculos
from gateway.main import app
from services.ms1_auth.schemas.auth import (
    LoginSolicitud as Ms1LoginSolicitud,
    RegistroClienteSolicitud as Ms1RegistroClienteSolicitud,
    TokenRespuesta as Ms1TokenRespuesta,
    UsuarioRespuesta as Ms1UsuarioRespuesta,
)
from services.ms2_taller.config import settings as ms2_settings
from services.ms2_taller.db import get_db as get_db_ms2
from services.ms2_taller.main import app as ms2_app
from services.ms2_taller.models.estado_orden import ESTADOS_ORDEN
from services.ms2_taller.schemas.vehiculo import (
    VehiculoActualizar as Ms2VehiculoActualizar,
    VehiculoCrear as Ms2VehiculoCrear,
    VehiculoRespuesta as Ms2VehiculoRespuesta,
)
from services.ms2_taller.schemas.orden import (
    AsignacionMecanicoActualizar as Ms2AsignacionMecanicoActualizar,
    CambioEstadoSolicitud as Ms2CambioEstadoSolicitud,
    HistorialEstadoRespuesta as Ms2HistorialEstadoRespuesta,
    OrdenCrear as Ms2OrdenCrear,
    OrdenRespuesta as Ms2OrdenRespuesta,
)
from shared.auth import NombreRol, crear_token_acceso
from shared.openapi_ordenes import ESTADOS_DOCUMENTADOS

_ENDPOINTS_ESPERADOS = {
    ("/api/auth/register", "post"),
    ("/api/auth/login", "post"),
    ("/api/auth/me", "get"),
    ("/api/vehiculos", "post"),
    ("/api/vehiculos", "get"),
    ("/api/vehiculos/asignados", "get"),
    ("/api/vehiculos/{vehiculo_id}", "get"),
    ("/api/vehiculos/{vehiculo_id}", "patch"),
    ("/api/ordenes", "post"),
    ("/api/ordenes", "get"),
    ("/api/ordenes/{orden_id}", "get"),
    ("/api/ordenes/{orden_id}/mecanico", "put"),
    ("/api/ordenes/{orden_id}/historial", "get"),
    ("/api/ordenes/{orden_id}/estado", "patch"),
    ("/api/ordenes/{orden_id}/decisiones-presupuesto", "post"),
    ("/api/presupuestos/decisiones/{decision_id}", "get"),
    ("/api/presupuestos/decisiones/{decision_id}/aplicacion", "post"),
}

_PUBLICOS = {"/api/auth/register", "/api/auth/login"}
_PROTEGIDOS = {
    "/api/auth/me",
    "/api/vehiculos",
    "/api/vehiculos/asignados",
    "/api/vehiculos/{vehiculo_id}",
    "/api/ordenes",
    "/api/ordenes/{orden_id}",
    "/api/ordenes/{orden_id}/mecanico",
    "/api/ordenes/{orden_id}/historial",
    "/api/ordenes/{orden_id}/estado",
    "/api/ordenes/{orden_id}/decisiones-presupuesto",
    "/api/presupuestos/decisiones/{decision_id}",
    "/api/presupuestos/decisiones/{decision_id}/aplicacion",
}


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


@pytest.fixture
def esquema(gateway: TestClient) -> dict:
    respuesta = gateway.get("/openapi.json")
    assert respuesta.status_code == 200
    return respuesta.json()


def _operaciones_documentadas(esquema: dict) -> dict[tuple[str, str], dict]:
    """Devuelve {(ruta, método): operación} de los endpoints de negocio."""
    return {
        (ruta, metodo): operacion
        for ruta, item in esquema["paths"].items()
        for metodo in ("get", "post", "put", "patch", "delete")
        if (operacion := item.get(metodo)) is not None
        if "/api/" in ruta and not ruta.startswith("/api/health")
    }


def test_openapi_responde_con_metadatos(esquema: dict) -> None:
    assert esquema["info"]["title"] == "SGTM — API Gateway"
    assert esquema["info"]["version"] == "0.1.0"
    assert esquema["openapi"].startswith("3.")


def test_estan_los_endpoints_con_sus_metodos(esquema: dict) -> None:
    operaciones = set(_operaciones_documentadas(esquema))
    assert operaciones == _ENDPOINTS_ESPERADOS


def test_proxy_generico_no_aparece(esquema: dict) -> None:
    assert not any("{ruta" in ruta or "{path" in ruta for ruta in esquema["paths"])


def test_seguridad_bearer_en_protegidos_y_no_en_publicos(esquema: dict) -> None:
    operaciones = _operaciones_documentadas(esquema)
    for ruta, metodo in _ENDPOINTS_ESPERADOS:
        seguridad = operaciones[(ruta, metodo)]["security"]
        esperado = (
            [{"bearerAuth": []}] if ruta in _PROTEGIDOS else []
        )
        assert seguridad == esperado, f"{metodo.upper()} {ruta} con security {seguridad}"

    assert "security" not in esquema
    assert (
        esquema["components"]["securitySchemes"]["bearerAuth"]["type"] == "http"
    )
    assert esquema["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"


def test_health_e_indice_publicos_no_exigen_token(esquema: dict) -> None:
    # Al no haber seguridad global, /, /api/health y /api/health/servicios quedan
    # públicos: no deben declarar security ni mostrar candado en Swagger.
    assert "security" not in esquema["paths"]["/"]["get"]
    assert "security" not in esquema["paths"]["/api/health"]["get"]
    assert "security" not in esquema["paths"]["/api/health/servicios"]["get"]


def test_errores_404_y_500_distinguen_gateway_de_microservicio(esquema: dict) -> None:
    operaciones = _operaciones_documentadas(esquema)
    # En estas operaciones el 404 también puede venir de MS2 (perfil o recurso
    # ausente): su esquema admite ErrorRespuesta y ErrorDetalle.
    operaciones_con_404_ms = {
        ("/api/vehiculos", "post"),
        ("/api/vehiculos", "get"),
        ("/api/vehiculos/{vehiculo_id}", "get"),
        ("/api/vehiculos/{vehiculo_id}", "patch"),
        ("/api/ordenes", "post"),
        ("/api/ordenes/{orden_id}", "get"),
        ("/api/ordenes/{orden_id}/mecanico", "put"),
        ("/api/ordenes/{orden_id}/historial", "get"),
        ("/api/ordenes/{orden_id}/estado", "patch"),
        ("/api/ordenes/{orden_id}/decisiones-presupuesto", "post"),
        ("/api/presupuestos/decisiones/{decision_id}", "get"),
        ("/api/presupuestos/decisiones/{decision_id}/aplicacion", "post"),
    }
    for ruta, metodo in _ENDPOINTS_ESPERADOS:
        respuestas = operaciones[(ruta, metodo)]["responses"]
        for estado in ("404", "502", "500"):
            esquema_respuesta = respuestas[estado]["content"]["application/json"][
                "schema"
            ]
            if estado == "500" or (
                estado == "404" and (ruta, metodo) in operaciones_con_404_ms
            ):
                referencias = {
                    item["$ref"] for item in esquema_respuesta["oneOf"]
                }
                assert referencias == {
                    "#/components/schemas/ErrorRespuesta",
                    "#/components/schemas/ErrorDetalle",
                }, f"{metodo.upper()} {ruta} {estado}"
            else:
                assert (
                    esquema_respuesta["$ref"]
                    == "#/components/schemas/ErrorRespuesta"
                ), f"{metodo.upper()} {ruta} {estado}"


def test_errores_de_los_microservicios_usan_formato_detalle(esquema: dict) -> None:
    operaciones = _operaciones_documentadas(esquema)
    for ruta, metodo in _ENDPOINTS_ESPERADOS:
        respuestas = operaciones[(ruta, metodo)]["responses"]
        for estado in ("401", "403", "409", "422"):
            if estado not in respuestas:
                continue
            esquema_respuesta = respuestas[estado]["content"]["application/json"][
                "schema"
            ]
            assert esquema_respuesta["$ref"] == "#/components/schemas/ErrorDetalle"


def test_body_obligatorio_donde_corresponde(esquema: dict) -> None:
    operaciones = _operaciones_documentadas(esquema)
    con_cuerpo = {
        ("/api/auth/register", "post"): "RegistroSolicitud",
        ("/api/auth/login", "post"): "LoginSolicitud",
        ("/api/vehiculos", "post"): "VehiculoCrear",
        ("/api/vehiculos/{vehiculo_id}", "patch"): "VehiculoActualizar",
        ("/api/ordenes", "post"): "OrdenCrear",
        (
            "/api/ordenes/{orden_id}/mecanico",
            "put",
        ): "AsignacionMecanicoActualizar",
        ("/api/ordenes/{orden_id}/estado", "patch"): "CambioEstadoSolicitud",
        ("/api/ordenes/{orden_id}/decisiones-presupuesto", "post"): "DecisionOrdenSolicitud",
    }
    for (ruta, metodo), ref in con_cuerpo.items():
        esquema_cuerpo = operaciones[(ruta, metodo)]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        assert esquema_cuerpo["$ref"] == f"#/components/schemas/{ref}"
    for (ruta, metodo) in (
        ("/api/auth/me", "get"),
        ("/api/vehiculos", "get"),
        ("/api/vehiculos/asignados", "get"),
        ("/api/vehiculos/{vehiculo_id}", "get"),
        ("/api/ordenes", "get"),
        ("/api/ordenes/{orden_id}", "get"),
        ("/api/ordenes/{orden_id}/historial", "get"),
    ):
        assert "requestBody" not in operaciones[(ruta, metodo)]


def test_docs_y_swagger_cargan(gateway: TestClient) -> None:
    assert gateway.get("/docs").status_code == 200
    assert gateway.get("/redoc").status_code == 200


@pytest.mark.parametrize(
    ("contrato", "real"),
    [
        (contratos_auth.RegistroSolicitud, Ms1RegistroClienteSolicitud),
        (contratos_auth.LoginSolicitud, Ms1LoginSolicitud),
        (contratos_auth.UsuarioRespuesta, Ms1UsuarioRespuesta),
        (contratos_auth.TokenRespuesta, Ms1TokenRespuesta),
        (contratos_vehiculos.VehiculoCrear, Ms2VehiculoCrear),
        (contratos_vehiculos.VehiculoActualizar, Ms2VehiculoActualizar),
        (contratos_vehiculos.VehiculoRespuesta, Ms2VehiculoRespuesta),
        (contratos_ordenes.OrdenCrear, Ms2OrdenCrear),
        (
            contratos_ordenes.AsignacionMecanicoActualizar,
            Ms2AsignacionMecanicoActualizar,
        ),
        (contratos_ordenes.OrdenRespuesta, Ms2OrdenRespuesta),
        (
            contratos_ordenes.CambioEstadoSolicitud,
            Ms2CambioEstadoSolicitud,
        ),
        (
            contratos_ordenes.HistorialEstadoRespuesta,
            Ms2HistorialEstadoRespuesta,
        ),
    ],
)
def test_contrato_coincide_con_esquema_real(contrato, real) -> None:
    """Las copias de la Gateway no se desactualizan respecto a MS1/MS2.

    Se comparan los campos y su obligatoriedad. No se compara el tipo exacto
    (la Gateway usa str en lugar de EmailStr o del enum de roles, para no
    importar código de los microservicios).
    """
    assert set(contrato.model_fields) == set(real.model_fields)
    for nombre, campo_real in real.model_fields.items():
        assert (
            contrato.model_fields[nombre].is_required() == campo_real.is_required()
        ), f"El campo '{nombre}' cambió su obligatoriedad"


def test_componentes_incluyen_contratos_y_formato_comun(esquema: dict) -> None:
    schemas = esquema["components"]["schemas"]
    for nombre in (
        "RegistroSolicitud",
        "LoginSolicitud",
        "UsuarioRespuesta",
        "TokenRespuesta",
        "VehiculoCrear",
        "VehiculoActualizar",
        "VehiculoRespuesta",
        "OrdenCrear",
        "AsignacionMecanicoActualizar",
        "OrdenRespuesta",
        "CambioEstadoSolicitud",
        "HistorialEstadoRespuesta",
        "ErrorRespuesta",
        "DetalleError",
        "ErrorDetalle",
    ):
        assert nombre in schemas
    # Los 422 de FastAPI ponen una lista de errores en detail, no un string.
    detalle = schemas["ErrorDetalle"]["properties"]["detail"]
    assert detalle["oneOf"] == [
        {"type": "string"},
        {"type": "array", "items": {"type": "object"}},
    ]


def test_contrato_detalla_email_y_roles(esquema: dict) -> None:
    schemas = esquema["components"]["schemas"]
    email_login = schemas["LoginSolicitud"]["properties"]["email"]
    assert email_login["format"] == "email"
    roles = schemas["UsuarioRespuesta"]["properties"]["roles"]
    assert roles["items"]["enum"] == ["cliente", "mecanico", "administrador"]


def test_contrato_vehiculo_no_inventa_formato_o_rangos(esquema: dict) -> None:
    propiedades_crear = esquema["components"]["schemas"]["VehiculoCrear"][
        "properties"
    ]
    patente = propiedades_crear["patente"]
    assert patente["minLength"] == 1
    assert "maxLength" not in patente
    assert "pattern" not in patente

    for campo in ("anio", "kilometraje"):
        contrato = propiedades_crear[campo]
        assert "minimum" not in contrato
        assert "maximum" not in contrato


def test_contrato_ordenes_refleja_flujo_implementado(esquema: dict) -> None:
    schemas = esquema["components"]["schemas"]
    assert schemas["OrdenCrear"]["additionalProperties"] is False
    assert schemas["OrdenCrear"]["properties"]["vehiculo_id"][
        "exclusiveMinimum"
    ] == 0
    assert schemas["AsignacionMecanicoActualizar"]["additionalProperties"] is False
    assert schemas["AsignacionMecanicoActualizar"]["properties"]["mecanico_id"][
        "exclusiveMinimum"
    ] == 0
    observacion = schemas["AsignacionMecanicoActualizar"]["properties"][
        "observacion"
    ]
    assert any(variante.get("minLength") == 1 for variante in observacion["anyOf"])

    paths = esquema["paths"]
    descripcion_listado = paths["/api/ordenes"]["get"]["description"]
    assert "Administrador ve todas" in descripcion_listado
    assert "Cliente" in descripcion_listado
    assert "Mecánico" in descripcion_listado
    assert "multirol" in descripcion_listado

    descripcion_asignacion = paths["/api/ordenes/{orden_id}/mecanico"]["put"][
        "description"
    ]
    assert "Recibido a Esperando diagnóstico" in descripcion_asignacion
    assert "reasignación conserva el estado" in descripcion_asignacion
    assert "Entregado y Cancelado" in descripcion_asignacion

    cambio = schemas["CambioEstadoSolicitud"]
    assert cambio["additionalProperties"] is False
    assert cambio["properties"]["estado_destino"]["exclusiveMinimum"] == 0
    assert "observacion" not in cambio["required"]
    assert "Obligatoria al pasar a Cancelado" in (
        cambio["properties"]["observacion"]["description"]
    )
    assert "Cancelado exige una observación" in (
        paths["/api/ordenes/{orden_id}/estado"]["patch"]["description"]
    )
    assert paths["/api/ordenes/{orden_id}/estado"]["patch"]["requestBody"][
        "content"
    ]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/CambioEstadoSolicitud"
    )
    assert paths["/api/ordenes/{orden_id}/estado"]["patch"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]["$ref"] == "#/components/schemas/OrdenRespuesta"

    assert (
        paths["/api/ordenes/{orden_id}/historial"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]["items"]["$ref"]
        == "#/components/schemas/HistorialEstadoRespuesta"
    )


@pytest.mark.parametrize("aplicacion,prefijo", [(app, "/api"), (ms2_app, "")])
def test_ejemplos_ordenes_y_catalogo_en_ambos_openapi(aplicacion, prefijo: str) -> None:
    esquema = aplicacion.openapi()
    OpenAPI.model_validate(esquema)
    assert ESTADOS_DOCUMENTADOS == ESTADOS_ORDEN
    assert len(ESTADOS_DOCUMENTADOS) == 8
    contrato = esquema["components"]["schemas"]["OrdenRespuesta"]
    estado = contrato["properties"]["estado_codigo"]
    assert estado["examples"] == list(ESTADOS_ORDEN)
    for codigo, nombre in ESTADOS_ORDEN.items():
        assert f"{codigo} = {nombre}" in estado["description"]

    for ruta, metodo, codigo in (
        ("/ordenes", "post", "201"),
        ("/ordenes", "get", "200"),
        ("/ordenes/{orden_id}", "get", "200"),
        ("/ordenes/{orden_id}/mecanico", "put", "200"),
    ):
        respuestas = esquema["paths"][prefijo + ruta][metodo]["responses"]
        ejemplos = respuestas[codigo]["content"]["application/json"]["examples"]
        for ejemplo in ejemplos.values():
            valor = ejemplo["value"]
            ordenes = valor if isinstance(valor, list) else [valor]
            for orden in ordenes:
                Ms2OrdenRespuesta.model_validate(orden)
                assert orden["estado_codigo"] in ESTADOS_ORDEN
                if metodo == "post":
                    assert orden["estado_codigo"] == 1
                    assert orden["mecanico_actual_id"] is None
                if metodo == "put":
                    assert orden["estado_codigo"] == 2
                    assert orden["mecanico_actual_id"] is not None
        assert "sin_token" in respuestas["401"]["content"]["application/json"][
            "examples"
        ]
        if metodo in ("post", "put"):
            for error in ("403", "404", "422"):
                assert respuestas[error]["content"]["application/json"]["examples"]
        elif "{orden_id}" in ruta:
            assert respuestas["404"]["content"]["application/json"]["examples"]
            assert respuestas["422"]["content"]["application/json"]["examples"]
    assert [orden["estado_codigo"] for orden in contrato["examples"]] == [1, 2]


def test_ejemplos_errores_coinciden_con_respuestas_reales_ms2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secreto = SecretStr("secreto-solo-pruebas-openapi-scrum-357-123456")
    monkeypatch.setattr(ms2_settings, "JWT_SECRET_KEY", secreto)

    def db_sin_consultas():
        # Estos rechazos ocurren antes de consultar o escribir en la base.
        yield None

    monkeypatch.setitem(ms2_app.dependency_overrides, get_db_ms2, db_sin_consultas)
    token_admin = crear_token_acceso(
        99, [NombreRol.ADMINISTRADOR], clave_secreta=secreto.get_secret_value(),
    )
    token_cliente = crear_token_acceso(
        10, [NombreRol.CLIENTE], clave_secreta=secreto.get_secret_value(),
    )
    headers_admin = {"Authorization": f"Bearer {token_admin}"}
    headers_cliente = {"Authorization": f"Bearer {token_cliente}"}
    casos = (
        ("/ordenes", "post", "401", "sin_token", {}, {"vehiculo_id": 12}),
        (
            "/ordenes", "post", "401", "token_invalido",
            {"Authorization": "Bearer invalido"}, {"vehiculo_id": 12},
        ),
        (
            "/ordenes", "post", "403", "rol_no_autorizado",
            headers_cliente, {"vehiculo_id": 12},
        ),
        (
            "/ordenes", "post", "422", "id_no_positivo",
            headers_admin, {"vehiculo_id": 0},
        ),
        (
            "/ordenes/{orden_id}/mecanico", "put", "422", "id_no_positivo",
            headers_admin, {"mecanico_id": 0},
        ),
        (
            "/ordenes/{orden_id}", "get", "422", "id_invalido",
            headers_admin, None,
        ),
    )
    esquemas = [(app.openapi(), "/api"), (ms2_app.openapi(), "")]
    with TestClient(ms2_app) as cliente:
        for ruta, metodo, codigo, nombre, headers, body in casos:
            url = ruta.replace("{orden_id}", "abc" if metodo == "get" else "31")
            respuesta = cliente.request(metodo, url, headers=headers, json=body)
            assert respuesta.status_code == int(codigo)
            for esquema, prefijo in esquemas:
                ejemplo = esquema["paths"][prefijo + ruta][metodo]["responses"][codigo][
                    "content"
                ]["application/json"]["examples"][nombre]["value"]
                assert respuesta.json() == ejemplo


@pytest.mark.parametrize("aplicacion,prefijo", [(app, "/api"), (ms2_app, "")])
def test_openapi_historial_publica_lista_protegida_y_errores(aplicacion, prefijo) -> None:
    esquema = aplicacion.openapi()
    operacion = esquema["paths"][f"{prefijo}/ordenes/{{orden_id}}/historial"]["get"]
    assert operacion["security"]
    assert "requestBody" not in operacion
    respuesta = operacion["responses"]["200"]["content"]["application/json"]["schema"]
    assert respuesta["type"] == "array"
    assert respuesta["items"] == {"$ref": "#/components/schemas/HistorialEstadoRespuesta"}
    assert {"200", "401", "404", "422", "500"} <= set(operacion["responses"])



def test_contrato_historial_coincide_en_tipos_y_nulabilidad() -> None:
    def tipos(valor):
        if isinstance(valor, dict):
            return {
                clave: tipos(contenido) for clave, contenido in valor.items()
                if clave not in {"title", "description", "examples"}
            }
        if isinstance(valor, list):
            return [tipos(item) for item in valor]
        return valor

    gateway_schema = contratos_ordenes.HistorialEstadoRespuesta.model_json_schema()
    ms2_schema = Ms2HistorialEstadoRespuesta.model_json_schema()
    assert set(gateway_schema["required"]) == set(ms2_schema["required"])
    assert tipos(gateway_schema["properties"]) == tipos(ms2_schema["properties"])
    assert gateway_schema["properties"]["origen"]["enum"] == ["usuario", "sistema"]


def test_coordinacion_publica_contrato_minimo_y_error_reintentable(esquema: dict) -> None:
    from shared.contratos_decisiones import (
        AplicacionDecisionRespuesta, DecisionOrdenSolicitud, DecisionPresupuestoVerificada,
    )
    schemas = esquema["components"]["schemas"]
    for modelo in (AplicacionDecisionRespuesta, DecisionOrdenSolicitud, DecisionPresupuestoVerificada):
        assert schemas[modelo.__name__]["properties"] == modelo.model_json_schema()["properties"]
    solicitud = schemas["DecisionOrdenSolicitud"]
    assert set(solicitud["properties"]) == {"decision_id"}
    assert solicitud["additionalProperties"] is False
    reintento = esquema["paths"]["/api/presupuestos/decisiones/{decision_id}/aplicacion"]["post"]
    refs = reintento["responses"]["503"]["content"]["application/json"]["schema"]["oneOf"]
    assert {ref["$ref"] for ref in refs} == {
        "#/components/schemas/DecisionAplicacionPendiente", "#/components/schemas/ErrorRespuesta",
    }
    assert reintento["security"] == [{"bearerAuth": []}]
    parametros = esquema["paths"]["/api/ordenes/{orden_id}"]["get"]["parameters"]
    propiedad = next(p for p in parametros if p["name"] == "solo_propietario")
    assert propiedad["in"] == "query" and propiedad["schema"]["default"] is False
