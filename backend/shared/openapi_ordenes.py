"""Ejemplos documentales de órdenes compartidos por Gateway y MS2.

No importa servicios ni altera modelos, validación o respuestas HTTP reales.
El catálogo documental se contrasta con el catálogo de MS2 en las pruebas.
"""

from __future__ import annotations

from copy import deepcopy

ESTADOS_DOCUMENTADOS = {
    1: "Recibido",
    2: "Esperando diagnóstico",
    3: "Esperando aprobación de presupuesto",
    4: "Esperando repuestos",
    5: "En reparación",
    6: "Listo",
    7: "Entregado",
    8: "Cancelado",
}

_RECIBIDO = {
    "orden_id": 31,
    "vehiculo_id": 12,
    "ingreso_id": 18,
    "estado_codigo": 1,
    "mecanico_actual_id": None,
    "creado_por_id": 99,
    "creado_en": "2026-09-28T10:30:00-03:00",
    "actualizado_en": "2026-09-28T10:30:00-03:00",
}
_DIAGNOSTICO = {
    **_RECIBIDO,
    "estado_codigo": 2,
    "mecanico_actual_id": 50,
    "actualizado_en": "2026-09-28T11:00:00-03:00",
}


def _ejemplo(resumen: str, valor: object) -> dict:
    return {"summary": resumen, "value": valor}


def _payload_invalido(campo: str) -> dict:
    return {
        "detail": [
            {
                "type": "greater_than",
                "loc": ["body", campo],
                "msg": "Input should be greater than 0",
                "input": 0,
                "ctx": {"gt": 0},
            }
        ]
    }


def _completar_errores(
    respuestas: dict,
    errores: dict[str, dict[str, dict]],
) -> None:
    """Agrega ejemplos documentales a respuestas de error ya declaradas.

    MS2 declara algunos errores solo con description. Completar su cuerpo
    documental sin reemplazar los esquemas ya publicados.
    """

    for codigo, ejemplos in errores.items():
        contenido = respuestas[codigo].setdefault("content", {})
        media = contenido.setdefault(
            "application/json",
            {
                "schema": {
                    "type": "object",
                    "properties": {"detail": {"type": "string"}},
                    "required": ["detail"],
                }
            },
        )
        media["examples"] = deepcopy(ejemplos)


def agregar_ejemplos_ordenes(esquema: dict, *, prefijo: str = "") -> None:
    """Enriquece únicamente OpenAPI; conserva esquemas y seguridad existentes."""
    contrato = esquema["components"]["schemas"]["OrdenRespuesta"]
    contrato["examples"] = deepcopy([_RECIBIDO, _DIAGNOSTICO])
    estado = contrato["properties"]["estado_codigo"]
    estado["description"] = (
        "Código del estado oficial: "
        + "; ".join(
            f"{codigo} = {nombre}" for codigo, nombre in ESTADOS_DOCUMENTADOS.items()
        )
        + ". El catálogo no implica que exista un endpoint para cada transición."
    )
    estado["examples"] = list(ESTADOS_DOCUMENTADOS)

    operaciones = (
        ("/ordenes", "post", "201"),
        ("/ordenes", "get", "200"),
        ("/ordenes/{orden_id}", "get", "200"),
        ("/ordenes/{orden_id}/mecanico", "put", "200"),
    )
    for ruta, metodo, codigo_ok in operaciones:
        respuestas = esquema["paths"][f"{prefijo}{ruta}"][metodo]["responses"]
        ejemplos_ok = {
            "recibido": _ejemplo("Recibido, sin mecánico", _RECIBIDO),
            "esperando_diagnostico": _ejemplo(
                "Esperando diagnóstico, con mecánico", _DIAGNOSTICO
            ),
        }
        if metodo == "post":
            ejemplos_ok.pop("esperando_diagnostico")
        elif ruta == "/ordenes" and metodo == "get":
            ejemplos_ok = {
                "ordenes_visibles": _ejemplo(
                    "Órdenes visibles en distintos estados",
                    [_RECIBIDO, {**_DIAGNOSTICO, "orden_id": 32}],
                ),
                "sin_ordenes": _ejemplo("Sin órdenes visibles", []),
            }
        elif metodo == "put":
            ejemplos_ok = {
                "primera_asignacion": ejemplos_ok["esperando_diagnostico"],
                "reasignacion": _ejemplo(
                    "Reasignación que conserva Esperando diagnóstico",
                    {**_DIAGNOSTICO, "mecanico_actual_id": 51},
                ),
            }
        respuestas[codigo_ok]["content"]["application/json"]["examples"] = deepcopy(
            ejemplos_ok
        )

        errores = {
            "401": {
                "sin_token": _ejemplo(
                    "Token ausente", {"detail": "No se proporcionó un token de acceso"}
                ),
                "token_invalido": _ejemplo(
                    "Token inválido o expirado", {"detail": "Token inválido o expirado"}
                ),
            },
        }
        if metodo in ("post", "put"):
            campo = "vehiculo_id" if metodo == "post" else "mecanico_id"
            errores["403"] = {
                "rol_no_autorizado": _ejemplo(
                    "Usuario autenticado sin rol Administrador",
                    {"detail": "No tienes permiso para realizar esta operación"},
                )
            }
            errores["422"] = {
                "id_no_positivo": _ejemplo(
                    f"{campo} igual a cero", _payload_invalido(campo)
                )
            }
        elif "{orden_id}" in ruta:
            errores["422"] = {
                "id_invalido": _ejemplo(
                    "orden_id no es un entero",
                    {
                        "detail": [{
                            "type": "int_parsing",
                            "loc": ["path", "orden_id"],
                            "msg": (
                                "Input should be a valid integer, "
                                "unable to parse string as an integer"
                            ),
                            "input": "abc",
                        }]
                    },
                )
            }
        if metodo == "post" or "{orden_id}" in ruta:
            detalle = (
                "Vehículo no encontrado" if metodo == "post" else "Orden no encontrada"
            )
            errores["404"] = {"recurso_ausente": _ejemplo(detalle, {"detail": detalle})}
        if metodo == "put":
            errores["409"] = {
                "autoasignacion": _ejemplo(
                    "Administrador con rol Mecánico intenta autoasignarse",
                    {"detail": "Un mecánico no puede autoasignarse una orden"},
                ),
                "orden_terminal": _ejemplo(
                    "Orden entregada o cancelada",
                    {"detail": "No se puede cambiar el mecánico de una orden terminal"},
                ),
            }
        _completar_errores(respuestas, errores)

    _agregar_ejemplos_historial_y_estado(esquema, prefijo=prefijo)


def _agregar_ejemplos_historial_y_estado(esquema: dict, *, prefijo: str) -> None:
    """Ejemplos de los endpoints agregados: historial consultable y cambio de estado."""

    ruta_historial = f"{prefijo}/ordenes/{{orden_id}}/historial"
    if ruta_historial in esquema["paths"]:
        respuestas = esquema["paths"][ruta_historial]["get"]["responses"]
        respuestas["200"]["content"]["application/json"]["examples"] = deepcopy(
            {
                "con_historial": _ejemplo(
                    "Dos transiciones registradas",
                    [
                        {
                            "historial_id": 41,
                            "orden_id": 31,
                            "estado_anterior": 1,
                            "estado_nuevo": 2,
                            "actor_usuario_id": 50,
                            "origen": "usuario",
                            "fecha_hora": "2026-09-28T11:00:00-03:00",
                            "observacion": "Inicia evaluación técnica",
                        },
                        {
                            "historial_id": 42,
                            "orden_id": 31,
                            "estado_anterior": 2,
                            "estado_nuevo": 3,
                            "actor_usuario_id": 50,
                            "origen": "usuario",
                            "fecha_hora": "2026-09-28T12:15:00-03:00",
                            "observacion": None,
                        },
                    ],
                ),
                "sin_cambios": _ejemplo("Orden sin transiciones", []),
            }
        )
        _completar_errores(
            respuestas,
            {
                "404": {
                    "recurso_ausente": _ejemplo(
                        "Orden no encontrada", {"detail": "Orden no encontrada"}
                    )
                }
            },
        )

    ruta_estado = f"{prefijo}/ordenes/{{orden_id}}/estado"
    if ruta_estado in esquema["paths"]:
        respuestas = esquema["paths"][ruta_estado]["patch"]["responses"]
        respuestas["200"]["content"]["application/json"]["examples"] = deepcopy(
            {
                "esperando_diagnostico": _ejemplo(
                    "Recibido a Esperando diagnóstico", _DIAGNOSTICO
                )
            }
        )
        _completar_errores(
            respuestas,
            {
                "403": {
                    "rol_no_autorizado": _ejemplo(
                        "Usuario sin rol Administrador ni orden asignada",
                        {
                            "detail": (
                                "No tienes permiso para cambiar el estado "
                                "de esta orden"
                            )
                        },
                    )
                },
                "404": {
                    "recurso_ausente": _ejemplo(
                        "Orden no encontrada", {"detail": "Orden no encontrada"}
                    )
                },
                "409": {
                    "transicion_no_permitida": _ejemplo(
                        "Transición no declarada",
                        {
                            "detail": (
                                "Transición no permitida: "
                                "Recibido -> En reparación"
                            )
                        },
                    ),
                    "orden_terminal": _ejemplo(
                        "Orden entregada o cancelada",
                        {
                            "detail": (
                                "El estado Entregado es terminal y no admite "
                                "transiciones"
                            )
                        },
                    ),
                },
                "422": {
                    "estado_desconocido": _ejemplo(
                        "Estado de destino desconocido",
                        {"detail": "Estado de destino desconocido: 999"},
                    ),
                    "estado_no_positivo": _ejemplo(
                        "Estado de destino igual a cero",
                        _payload_invalido("estado_destino"),
                    ),
                },
            },
        )
