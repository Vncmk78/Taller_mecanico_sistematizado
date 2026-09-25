"""Pruebas de la documentación OpenAPI/Swagger de la Gateway (Semana 2, tarea 2).

Verifican que `/openapi.json` publica los 7 endpoints reales (auth y
vehículos) con sus contratos y seguridad, que el proxy genérico no aparece, y
que las copias del contrato de la Gateway (`gateway/contratos`) no se
desactualizan respecto a los esquemas reales de MS1 y MS2.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.contratos import auth as contratos_auth
from gateway.contratos import vehiculos as contratos_vehiculos
from gateway.main import app
from services.ms1_auth.schemas.auth import (
    LoginSolicitud as Ms1LoginSolicitud,
    RegistroClienteSolicitud as Ms1RegistroClienteSolicitud,
    TokenRespuesta as Ms1TokenRespuesta,
    UsuarioRespuesta as Ms1UsuarioRespuesta,
)
from services.ms2_taller.schemas.vehiculo import (
    VehiculoActualizar as Ms2VehiculoActualizar,
    VehiculoCrear as Ms2VehiculoCrear,
    VehiculoRespuesta as Ms2VehiculoRespuesta,
)

_ENDPOINTS_ESPERADOS = {
    ("/api/auth/register", "post"),
    ("/api/auth/login", "post"),
    ("/api/auth/me", "get"),
    ("/api/vehiculos", "post"),
    ("/api/vehiculos", "get"),
    ("/api/vehiculos/{vehiculo_id}", "get"),
    ("/api/vehiculos/{vehiculo_id}", "patch"),
}

_PUBLICOS = {"/api/auth/register", "/api/auth/login"}
_PROTEGIDOS = {
    "/api/auth/me",
    "/api/vehiculos",
    "/api/vehiculos/{vehiculo_id}",
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
        if "/api/" in ruta and ruta not in {"/api/health"}
    }


def test_openapi_responde_con_metadatos(esquema: dict) -> None:
    assert esquema["info"]["title"] == "SGTM — API Gateway"
    assert esquema["info"]["version"] == "0.1.0"
    assert esquema["openapi"].startswith("3.")


def test_estan_los_7_endpoints_con_sus_metodos(esquema: dict) -> None:
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
    # Al no haber seguridad global, / y /api/health quedan públicos: no deben
    # declarar security ni mostrar candado en Swagger.
    assert "security" not in esquema["paths"]["/"]["get"]
    assert "security" not in esquema["paths"]["/api/health"]["get"]


def test_errores_de_la_gateway_apuntan_a_errorrespuesta(esquema: dict) -> None:
    operaciones = _operaciones_documentadas(esquema)
    # En GET/PATCH /api/vehiculos/{vehiculo_id} el 404 puede venir del
    # microservicio: su esquema es oneOf [ErrorRespuesta, ErrorDetalle].
    vehiculos_con_404_ms = {
        ("/api/vehiculos/{vehiculo_id}", "get"),
        ("/api/vehiculos/{vehiculo_id}", "patch"),
    }
    for ruta, metodo in _ENDPOINTS_ESPERADOS:
        respuestas = operaciones[(ruta, metodo)]["responses"]
        for estado in ("404", "502", "500"):
            esquema_respuesta = respuestas[estado]["content"]["application/json"][
                "schema"
            ]
            if estado == "404" and (ruta, metodo) in vehiculos_con_404_ms:
                referencias = {
                    item["$ref"] for item in esquema_respuesta["oneOf"]
                }
                assert referencias == {
                    "#/components/schemas/ErrorRespuesta",
                    "#/components/schemas/ErrorDetalle",
                }, f"{metodo.upper()} {ruta} 404"
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
    }
    for (ruta, metodo), ref in con_cuerpo.items():
        esquema_cuerpo = operaciones[(ruta, metodo)]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        assert esquema_cuerpo["$ref"] == f"#/components/schemas/{ref}"
    for (ruta, metodo) in (("/api/auth/me", "get"), ("/api/vehiculos", "get"),
                           ("/api/vehiculos/{vehiculo_id}", "get")):
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