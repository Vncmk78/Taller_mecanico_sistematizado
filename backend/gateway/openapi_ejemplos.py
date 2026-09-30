"""Ejemplos y respuestas reutilizables del OpenAPI de la Gateway.

`gateway/openapi.py` arma el esquema con los contratos y llama a este módulo al
final, después de `shared.openapi_ordenes`, para agregar lo que se repite en casi
todas las operaciones:

* `components.examples`: los cuerpos reales de los errores de la Gateway y de los
  microservicios, referenciables por nombre desde `openapi.json`;
* `components.responses`: las respuestas comunes (`NoAutenticado`, `ErrorInterno`,
  `ServicioNoDisponible`, `GatewaySaturada` y `TiempoAgotado`);
* ejemplos de request y de response en las operaciones de Auth y Vehículos (las
  de Órdenes ya las documenta `shared.openapi_ordenes.py`);
* la cabecera `X-Request-ID` en las respuestas de todo `/api` y los ejemplos de
  los health checks.

Los textos de los errores de la Gateway se importan de `gateway.errores` para que
el ejemplo y el código que genera la respuesta no puedan divergir, y los de los
microservicios son los que realmente responden MS1 y MS2.

Todo es idempotente (se puede aplicar dos veces sin cambiar el resultado) y
ningún `examples` que ya exista en el documento se pisa, de modo que los
ejemplos de órdenes se conservan.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from gateway.errores import (
    ERROR_INTERNO,
    ERROR_MICROSERVICIO,
    GATEWAY_SATURADA,
    MENSAJE_ERROR_MICROSERVICIO,
    MENSAJE_GATEWAY_SATURADA,
    MENSAJE_METODO_NO_PERMITIDO,
    MENSAJE_RUTA_NO_ENCONTRADA,
    MENSAJE_SERVICIO_CAIDO,
    MENSAJE_TIEMPO_AGOTADO,
    METODO_NO_PERMITIDO,
    MICROSERVICIO_INALCANZABLE,
    RUTA_NO_ENCONTRADA,
    TIEMPO_AGOTADO,
)
from gateway.errores import _MENSAJE_ERROR_INTERNO as MENSAJE_ERROR_INTERNO

_JSON = "application/json"
_METODOS = ("get", "post", "put", "patch", "delete")

# Valores de ejemplo: nunca un token real ni una URL interna.
_REQUEST_ID = "abc-123"
_TOKEN_EJEMPLO = "eyJhbGciOiJIUzI1NiJ9.ejemplo.firma"


def _ejemplo(resumen: str, valor: Any, descripcion: str | None = None) -> dict[str, Any]:
    ejemplo: dict[str, Any] = {"summary": resumen, "value": valor}
    if descripcion is not None:
        ejemplo["description"] = descripcion
    return ejemplo


def _ref_ejemplo(nombre: str) -> dict[str, Any]:
    return {"$ref": f"#/components/examples/{nombre}"}


def _error_gateway(*, codigo: str, estado: int, detalle: str, ruta: str) -> dict[str, Any]:
    """Cuerpo real de un error generado por la propia Gateway."""
    return {
        "detail": detalle,
        "error": {
            "codigo": codigo,
            "estado": estado,
            "ruta": ruta,
            "request_id": _REQUEST_ID,
        },
    }


_EJEMPLOS_ERROR_GATEWAY: dict[str, dict[str, Any]] = {
    "error_ruta_no_encontrada": _ejemplo(
        "404 de la Gateway: el camino no existe",
        _error_gateway(
            codigo=RUTA_NO_ENCONTRADA,
            estado=404,
            detalle=MENSAJE_RUTA_NO_ENCONTRADA,
            ruta="/api/vehiculos/999",
        ),
        "La Gateway no enruta ese camino a ningún microservicio.",
    ),
    "error_metodo_no_permitido": _ejemplo(
        "405 de la Gateway: el método no existe en esa ruta",
        _error_gateway(
            codigo=METODO_NO_PERMITIDO,
            estado=405,
            detalle=MENSAJE_METODO_NO_PERMITIDO,
            ruta="/api/auth/login",
        ),
        "Ocurre al invocar un método que la ruta no declara.",
    ),
    "error_microservicio_no_disponible": _ejemplo(
        "502: el microservicio no respondió",
        _error_gateway(
            codigo=MICROSERVICIO_INALCANZABLE,
            estado=502,
            detalle=MENSAJE_SERVICIO_CAIDO,
            ruta="/api/vehiculos",
        ),
        "Conexión rechazada o microservicio caído.",
    ),
    "error_gateway_saturada": _ejemplo(
        "503: el pool de conexiones está agotado",
        _error_gateway(
            codigo=GATEWAY_SATURADA,
            estado=503,
            detalle=MENSAJE_GATEWAY_SATURADA,
            ruta="/api/vehiculos",
        ),
        "La Gateway no llegó a reenviar la petición.",
    ),
    "error_tiempo_agotado": _ejemplo(
        "504: el microservicio tardó demasiado",
        _error_gateway(
            codigo=TIEMPO_AGOTADO,
            estado=504,
            detalle=MENSAJE_TIEMPO_AGOTADO,
            ruta="/api/vehiculos",
        ),
        "Se agotó el timeout de lectura antes de recibir la respuesta.",
    ),
    "error_microservicio": _ejemplo(
        "Respuesta no JSON del microservicio, normalizada por la Gateway",
        _error_gateway(
            codigo=ERROR_MICROSERVICIO,
            estado=500,
            detalle=MENSAJE_ERROR_MICROSERVICIO,
            ruta="/api/vehiculos",
        ),
        "Conserva el estado HTTP que respondió el microservicio.",
    ),
    "error_interno_gateway": _ejemplo(
        "500: error no controlado dentro de la Gateway",
        _error_gateway(
            codigo=ERROR_INTERNO,
            estado=500,
            detalle=MENSAJE_ERROR_INTERNO,
            ruta="/api/vehiculos",
        ),
        "El cuerpo nunca muestra la excepción interna.",
    ),
}

_EJEMPLOS_ERROR_MICROSERVICIO: dict[str, dict[str, Any]] = {
    "detalle_token_ausente": _ejemplo(
        "401 sin cabecera Authorization",
        {"detail": "No se proporcionó un token de acceso"},
        "MS1 y MS2 responden además WWW-Authenticate: Bearer.",
    ),
    "detalle_token_invalido": _ejemplo(
        "401 con token inválido o expirado",
        {"detail": "Token inválido o expirado"},
    ),
    "detalle_credenciales_invalidas": _ejemplo(
        "401 de login con credenciales incorrectas",
        {"detail": "Correo o contraseña incorrectos"},
    ),
    "detalle_rol_insuficiente": _ejemplo(
        "403: se requiere rol Cliente (vehículos) o Administrador (órdenes)",
        {"detail": "No tienes permiso para realizar esta operación"},
        "El token es válido, pero el principal no tiene ninguno de los roles exigidos.",
    ),
    "detalle_vehiculo_no_encontrado": _ejemplo(
        "404 de vehículo inexistente o ajeno al cliente",
        {"detail": "Vehículo no encontrado"},
        "Un vehículo de otro cliente y uno inexistente responden lo mismo.",
    ),
    "detalle_perfil_cliente_ausente": _ejemplo(
        "404 sin perfil Cliente local en MS2",
        {"detail": "El usuario autenticado no tiene un perfil Cliente en MS2"},
    ),
    "detalle_patente_registrada": _ejemplo(
        "409 con la patente ya registrada",
        {"detail": "La patente ya está registrada"},
    ),
    "detalle_correo_registrado": _ejemplo(
        "409 con el correo ya registrado",
        {"detail": "El correo ya está registrado"},
    ),
    "detalle_validacion_registro_422": _ejemplo(
        "422 de validación del body de registro",
        {
            "detail": [
                {
                    "type": "value_error",
                    "loc": ["body", "email"],
                    "msg": (
                        "value is not a valid email address: "
                        "An email address must have an @-sign."
                    ),
                    "input": "no-es-un-correo",
                },
                {
                    "type": "string_too_short",
                    "loc": ["body", "password"],
                    "msg": "String should have at least 8 characters",
                    "input": "corta",
                },
            ]
        },
        "Pydantic v2 devuelve una lista de errores; `loc` indica el campo.",
    ),
    "detalle_validacion_vehiculo_422": _ejemplo(
        "422 de validación del body de vehículo",
        {
            "detail": [
                {
                    "type": "string_too_short",
                    "loc": ["body", "patente"],
                    "msg": "String should have at least 1 character",
                    "input": "",
                }
            ]
        },
    ),
}

_USUARIO_EJEMPLO: dict[str, Any] = {
    "id": 7,
    "email": "ana@correo.cl",
    "full_name": "Ana Pérez",
    "roles": ["cliente"],
    "is_active": True,
}

_VEHICULO_EJEMPLO: dict[str, Any] = {
    "vehiculo_id": 12,
    "patente": "AB1234",
    "marca": "Toyota",
    "modelo": "Corolla",
    "anio": 2018,
    "kilometraje": 45000,
}

_VEHICULO_ACTUALIZADO_EJEMPLO: dict[str, Any] = {
    **_VEHICULO_EJEMPLO,
    "modelo": "Corolla Cross",
}

_EJEMPLOS_AUTENTICACION: dict[str, Any] = {
    "token_ausente": _ref_ejemplo("detalle_token_ausente"),
    "token_invalido": _ref_ejemplo("detalle_token_invalido"),
}

# (ruta, método) -> {"cuerpo": ejemplos, "respuestas": {código: ejemplos}}.
# `/api/ordenes` no aparece a propósito: sus ejemplos son de
# `shared.openapi_ordenes.py` y esta función nunca los pisa.
_EJEMPLOS_OPERACIONES: dict[tuple[str, str], dict[str, Any]] = {
    ("/api/auth/register", "post"): {
        "cuerpo": {
            "registro": {
                "summary": "Body de registro (el rol lo asigna el servidor)",
                "value": {
                    "email": "ana@correo.cl",
                    "password": "clave-segura-123",
                    "full_name": "Ana Pérez",
                },
            }
        },
        "respuestas": {
            "201": {
                "usuario_registrado": {
                    "summary": "Cliente creado con rol Cliente",
                    "value": _USUARIO_EJEMPLO,
                }
            },
            "409": {"correo_registrado": _ref_ejemplo("detalle_correo_registrado")},
            "422": {
                "datos_invalidos": _ref_ejemplo("detalle_validacion_registro_422")
            },
        },
    },
    ("/api/auth/login", "post"): {
        "cuerpo": {
            "login": {
                "summary": "Body de login",
                "value": {"email": "ana@correo.cl", "password": "clave-segura-123"},
            }
        },
        "respuestas": {
            "200": {
                "token": {
                    "summary": "Token de ejemplo (no es un JWT real)",
                    "description": (
                        "El `access_token` es ficticio: sirve para ver el formato, "
                        "no habilita ninguna llamada."
                    ),
                    "value": {
                        "access_token": _TOKEN_EJEMPLO,
                        "token_type": "bearer",
                        "user": _USUARIO_EJEMPLO,
                    },
                }
            },
            "401": {
                "credenciales_invalidas": _ref_ejemplo(
                    "detalle_credenciales_invalidas"
                )
            },
        },
    },
    ("/api/auth/me", "get"): {
        "respuestas": {
            "200": {
                "usuario": {
                    "summary": "Usuario del token",
                    "value": _USUARIO_EJEMPLO,
                }
            },
            "401": _EJEMPLOS_AUTENTICACION,
        },
    },
    ("/api/vehiculos", "post"): {
        "cuerpo": {
            "vehiculo": {
                "summary": "Body de registro de vehículo",
                "value": {
                    "patente": "AB1234",
                    "marca": "Toyota",
                    "modelo": "Corolla",
                    "anio": 2018,
                    "kilometraje": 45000,
                },
            }
        },
        "respuestas": {
            "201": {
                "vehiculo_registrado": {
                    "summary": "Vehículo del cliente autenticado",
                    "value": _VEHICULO_EJEMPLO,
                }
            },
            "401": _EJEMPLOS_AUTENTICACION,
            "403": {"rol_insuficiente": _ref_ejemplo("detalle_rol_insuficiente")},
            "404": {
                "perfil_cliente_ausente": _ref_ejemplo("detalle_perfil_cliente_ausente")
            },
            "409": {"patente_registrada": _ref_ejemplo("detalle_patente_registrada")},
            "422": {
                "datos_invalidos": _ref_ejemplo("detalle_validacion_vehiculo_422")
            },
        },
    },
    ("/api/vehiculos", "get"): {
        "respuestas": {
            "200": {
                "lista": {
                    "summary": "Lista con un vehículo del cliente",
                    "value": [_VEHICULO_EJEMPLO],
                }
            },
            "401": _EJEMPLOS_AUTENTICACION,
            "403": {"rol_insuficiente": _ref_ejemplo("detalle_rol_insuficiente")},
            "404": {
                "perfil_cliente_ausente": _ref_ejemplo("detalle_perfil_cliente_ausente")
            },
        },
    },
    ("/api/vehiculos/asignados", "get"): {
        "respuestas": {
            "200": {
                "lista_asignados": {
                    "summary": "Lista con un vehículo asignado al mecánico",
                    "value": [_VEHICULO_EJEMPLO],
                }
            },
            "401": _EJEMPLOS_AUTENTICACION,
            "403": {"rol_insuficiente": _ref_ejemplo("detalle_rol_insuficiente")},
        },
    },
    ("/api/vehiculos/{vehiculo_id}", "get"): {
        "respuestas": {
            "200": {
                "vehiculo": {
                    "summary": "Vehículo consultado",
                    "value": _VEHICULO_EJEMPLO,
                }
            },
            "401": _EJEMPLOS_AUTENTICACION,
            "403": {"rol_insuficiente": _ref_ejemplo("detalle_rol_insuficiente")},
            "404": {
                "vehiculo_no_encontrado": _ref_ejemplo("detalle_vehiculo_no_encontrado")
            },
        },
    },
    ("/api/vehiculos/{vehiculo_id}", "patch"): {
        "cuerpo": {
            "actualizacion_parcial": {
                "summary": "Body de actualización parcial (al menos un campo)",
                "value": {"modelo": "Corolla Cross"},
            }
        },
        "respuestas": {
            "200": {
                "vehiculo_actualizado": {
                    "summary": "Vehículo con el campo modificado",
                    "value": _VEHICULO_ACTUALIZADO_EJEMPLO,
                }
            },
            "401": _EJEMPLOS_AUTENTICACION,
            "403": {"rol_insuficiente": _ref_ejemplo("detalle_rol_insuficiente")},
            "404": {
                "vehiculo_no_encontrado": _ref_ejemplo("detalle_vehiculo_no_encontrado")
            },
            "422": {
                "datos_invalidos": _ref_ejemplo("detalle_validacion_vehiculo_422")
            },
        },
    },
}

_CABECERA_X_REQUEST_ID: dict[str, Any] = {
    "description": (
        "Identificador de la petición. La Gateway lo genera si el cliente no "
        "envía uno válido; es el mismo valor de `error.request_id`."
    ),
    "schema": {"type": "string"},
    "example": _REQUEST_ID,
}

_CABECERA_WWW_AUTHENTICATE: dict[str, Any] = {
    "description": "El microservicio exige un token Bearer.",
    "schema": {"type": "string"},
    "example": "Bearer",
}

_CABECERA_RETRY_AFTER: dict[str, Any] = {
    "description": "Segundos que el cliente puede esperar antes de reintentar.",
    "schema": {"type": "integer"},
    "example": 1,
}

_CABECERA_CACHE_CONTROL: dict[str, Any] = {
    "description": "Los health checks no se cachean.",
    "schema": {"type": "string"},
    "example": "no-store",
}


def _respuesta_comun(
    *,
    descripcion: str,
    esquema: dict[str, Any],
    ejemplos: dict[str, Any],
    cabeceras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "description": descripcion,
        "headers": {**{"X-Request-ID": _CABECERA_X_REQUEST_ID}, **(cabeceras or {})},
        "content": {_JSON: {"schema": esquema, "examples": ejemplos}},
    }


_RESPUESTAS_REUTILIZABLES: dict[str, dict[str, Any]] = {
    "NoAutenticado": _respuesta_comun(
        descripcion=(
            "401 de MS1 o MS2: falta el token, expiró o su firma no es válida. "
            "El frontend debe limpiar la sesión y volver a iniciar sesión."
        ),
        esquema={"$ref": "#/components/schemas/ErrorDetalle"},
        ejemplos=dict(_EJEMPLOS_AUTENTICACION),
        cabeceras={"WWW-Authenticate": _CABECERA_WWW_AUTHENTICATE},
    ),
    "ErrorInterno": _respuesta_comun(
        descripcion=(
            "500: error no controlado de la Gateway (`ERROR_INTERNO`) o "
            "respuesta no JSON del microservicio (`ERROR_MICROSERVICIO`)."
        ),
        esquema={
            "oneOf": [
                {"$ref": "#/components/schemas/ErrorRespuesta"},
                {"$ref": "#/components/schemas/ErrorDetalle"},
            ]
        },
        ejemplos={
            "error_interno": _ref_ejemplo("error_interno_gateway"),
            "error_microservicio": _ref_ejemplo("error_microservicio"),
        },
    ),
    "ServicioNoDisponible": _respuesta_comun(
        descripcion="502: el microservicio no respondió (conexión o caída).",
        esquema={"$ref": "#/components/schemas/ErrorRespuesta"},
        ejemplos={
            "microservicio_no_disponible": _ref_ejemplo(
                "error_microservicio_no_disponible"
            )
        },
    ),
    "GatewaySaturada": _respuesta_comun(
        descripcion="503: el pool de conexiones de la Gateway está agotado.",
        esquema={"$ref": "#/components/schemas/ErrorRespuesta"},
        ejemplos={"gateway_saturada": _ref_ejemplo("error_gateway_saturada")},
        cabeceras={"Retry-After": _CABECERA_RETRY_AFTER},
    ),
    "TiempoAgotado": _respuesta_comun(
        descripcion="504: el microservicio tardó demasiado en responder.",
        esquema={"$ref": "#/components/schemas/ErrorRespuesta"},
        ejemplos={"tiempo_agotado": _ref_ejemplo("error_tiempo_agotado")},
    ),
}

_EJEMPLO_HEALTH: dict[str, Any] = {
    "summary": "La Gateway está viva",
    "value": {"status": "ok", "servicio": "gateway"},
}

_EJEMPLO_SERVICIOS_OK: dict[str, Any] = {
    "summary": "Los cuatro microservicios responden",
    "value": {
        "status": "ok",
        "gateway": "ok",
        "servicios": {
            "ms1_auth": {"estado": "ok", "latencia_ms": 3},
            "ms2_taller": {"estado": "ok", "latencia_ms": 4},
            "ms3_presupuestos": {"estado": "ok", "latencia_ms": 2},
            "ms4_evidencias": {"estado": "ok", "latencia_ms": 5},
        },
    },
}

_EJEMPLO_SERVICIOS_DEGRADADO: dict[str, Any] = {
    "summary": "503 con status degradado: MS3 caído y MS4 sin base",
    "value": {
        "status": "degradado",
        "gateway": "ok",
        "servicios": {
            "ms1_auth": {"estado": "ok", "latencia_ms": 3},
            "ms2_taller": {"estado": "ok", "latencia_ms": 4},
            "ms3_presupuestos": {"estado": "caido"},
            "ms4_evidencias": {"estado": "sin_base", "latencia_ms": 6, "codigo_http": 503},
        },
    },
}


def _componentes(esquema: dict[str, Any]) -> dict[str, Any]:
    return esquema.setdefault("components", {})


def _agregar_ejemplos(media: dict[str, Any] | None, ejemplos: dict[str, Any]) -> None:
    """Agrega ejemplos a un media type sin pisar los que ya existan.

    Los ejemplos que ya estaban (por ejemplo los de órdenes) tienen prioridad,
    de modo que aplicar dos veces el módulo deja el documento igual.
    """
    if media is None or not ejemplos:
        return
    nuevos = {nombre: deepcopy(ejemplo) for nombre, ejemplo in ejemplos.items()}
    media["examples"] = {**nuevos, **media.get("examples", {})}


def _agregar_cabecera(respuesta: dict[str, Any], cabecera: dict[str, Any]) -> None:
    respuesta["headers"] = {**cabecera, **respuesta.get("headers", {})}


def _media_cuerpo(operacion: dict[str, Any]) -> dict[str, Any] | None:
    cuerpo = operacion.get("requestBody")
    if not isinstance(cuerpo, dict):
        return None
    return cuerpo.get("content", {}).get(_JSON)


def _media_respuesta(operacion: dict[str, Any], codigo: str) -> dict[str, Any] | None:
    respuesta = operacion.get("responses", {}).get(codigo)
    if not isinstance(respuesta, dict):
        return None
    return respuesta.get("content", {}).get(_JSON)


def _es_negocio(ruta: str) -> bool:
    return ruta.startswith("/api/") and not ruta.startswith("/api/health")


def _aplicar_componentes(esquema: dict[str, Any]) -> None:
    componentes = _componentes(esquema)
    ejemplos = componentes.setdefault("examples", {})
    for nombre, ejemplo in {
        **_EJEMPLOS_ERROR_GATEWAY,
        **_EJEMPLOS_ERROR_MICROSERVICIO,
    }.items():
        ejemplos.setdefault(nombre, deepcopy(ejemplo))
    respuestas = componentes.setdefault("responses", {})
    for nombre, respuesta in _RESPUESTAS_REUTILIZABLES.items():
        respuestas.setdefault(nombre, deepcopy(respuesta))


def _aplicar_ejemplos_operaciones(esquema: dict[str, Any]) -> None:
    paths = esquema.get("paths", {})
    for (ruta, metodo), contenido in _EJEMPLOS_OPERACIONES.items():
        operacion = paths.get(ruta, {}).get(metodo)
        if not isinstance(operacion, dict):
            continue
        _agregar_ejemplos(_media_cuerpo(operacion), contenido.get("cuerpo", {}))
        for codigo, ejemplos in contenido.get("respuestas", {}).items():
            _agregar_ejemplos(_media_respuesta(operacion, codigo), ejemplos)


def _aplicar_ejemplos_errores_comunes(esquema: dict[str, Any]) -> None:
    """Ejemplos de 401, 404, 500 y 502 en cada operación de negocio.

    El 503 y el 504 se referencian con `$ref` a `GatewaySaturada` y
    `TiempoAgotado` desde `gateway/openapi.py`, así que aquí solo se completan
    las respuestas que siguen escritas en línea.
    """
    for ruta, item in esquema.get("paths", {}).items():
        if not _es_negocio(ruta):
            continue
        for metodo in _METODOS:
            operacion = item.get(metodo)
            if not isinstance(operacion, dict):
                continue
            for codigo, ejemplo in (
                ("401", _EJEMPLOS_AUTENTICACION),
                (
                    "404",
                    {"ruta_no_encontrada": _ref_ejemplo("error_ruta_no_encontrada")},
                ),
                (
                    "500",
                    {
                        "error_interno": _ref_ejemplo("error_interno_gateway"),
                        "error_microservicio": _ref_ejemplo("error_microservicio"),
                    },
                ),
                (
                    "502",
                    {
                        "microservicio_no_disponible": _ref_ejemplo(
                            "error_microservicio_no_disponible"
                        )
                    },
                ),
            ):
                _agregar_ejemplos(_media_respuesta(operacion, codigo), ejemplo)


def _documentar_health(esquema: dict[str, Any]) -> None:
    paths = esquema.get("paths", {})

    salud = paths.get("/api/health", {}).get("get")
    if isinstance(salud, dict):
        ok = salud.get("responses", {}).get("200")
        if isinstance(ok, dict):
            ok["description"] = (
                "La Gateway está viva. No consulta a los microservicios, por eso "
                "responde 200 aunque MS1 o MS2 estén caídos."
            )
            _agregar_ejemplos(
                ok.get("content", {}).get(_JSON), {"gateway_viva": _EJEMPLO_HEALTH}
            )

    servicios = paths.get("/api/health/servicios", {}).get("get")
    if not isinstance(servicios, dict):
        return
    respuestas = servicios.setdefault("responses", {})

    ok = respuestas.setdefault(
        "200", {"description": "", "content": {_JSON: {"schema": {}}}}
    )
    ok["description"] = (
        "Los cuatro microservicios respondieron a su health check dentro del timeout."
    )
    _agregar_cabecera(ok, {"Cache-Control": _CABECERA_CACHE_CONTROL})
    _agregar_ejemplos(
        ok.get("content", {}).get(_JSON), {"servicios_ok": _EJEMPLO_SERVICIOS_OK}
    )

    degradado = respuestas.setdefault(
        "503", {"description": "", "content": {_JSON: {"schema": {"type": "object"}}}}
    )
    degradado["description"] = (
        "Al menos un microservicio no respondió: `status` es `degradado`."
    )
    _agregar_cabecera(degradado, {"Cache-Control": _CABECERA_CACHE_CONTROL})
    _agregar_ejemplos(
        degradado.get("content", {}).get(_JSON),
        {"servicios_degradados": _EJEMPLO_SERVICIOS_DEGRADADO},
    )


def _documentar_x_request_id(esquema: dict[str, Any]) -> None:
    """Declara la cabecera `X-Request-ID` en todas las respuestas de `/api`."""
    for ruta, item in esquema.get("paths", {}).items():
        if not ruta.startswith("/api"):
            continue
        for metodo in _METODOS:
            operacion = item.get(metodo)
            if not isinstance(operacion, dict):
                continue
            for respuesta in operacion.get("responses", {}).values():
                # Las respuestas reutilizables (`$ref`) ya la declaran.
                if isinstance(respuesta, dict) and "$ref" not in respuesta:
                    _agregar_cabecera(respuesta, {"X-Request-ID": _CABECERA_X_REQUEST_ID})


def agregar_ejemplos_gateway(esquema: dict[str, Any]) -> None:
    """Agrega ejemplos, respuestas reutilizables y cabeceras al esquema dado.

    Se llama desde `gateway/openapi.py` al final de `construir_openapi`, después
    de `shared.openapi_ordenes.agregar_ejemplos_ordenes`, y se puede aplicar dos
    veces sin cambiar el resultado.
    """
    _aplicar_componentes(esquema)
    _aplicar_ejemplos_operaciones(esquema)
    _aplicar_ejemplos_errores_comunes(esquema)
    _documentar_health(esquema)
    _documentar_x_request_id(esquema)