// Fixtures SOLO para tests: copias literales de los cuerpos que devuelve y
// devuelve el backend hoy, para que el mapeo del frontend se pruebe contra
// datos reales y no contra payloads inventados.
//
// Cada grupo cita su origen para que se note cuando el contrato cambia:
//   - Éxitos: gateway/contratos/{vehiculos,ordenes,auth}.py y sus ejemplos, que
//     backend/tests/test_gateway_openapi.py compara con los esquemas reales.
//   - Errores: gateway/errores.py (formato propio) y los literales de
//     ms2_taller / ms1_auth citados en cada bloque.
// La producción nunca importa este archivo: consume solo respuestas reales.

// ---------------------------------------------------------------------------
// Éxitos
// ---------------------------------------------------------------------------

/** Ejemplo real de gateway/contratos/vehiculos.py:24 (_EJEMPLO_RESPUESTA). */
export const vehiculoRespuestaReal = {
    vehiculo_id: 12,
    cliente_id: 7,
    patente: 'AB1234',
    marca: 'Toyota',
    modelo: 'Corolla',
    anio: 2018,
    kilometraje: 45000,
};

/**
 * Mismo vehículo registrado sin año ni kilometraje. Ambos campos son
 * `int | None` en el esquema real (gateway/contratos/vehiculos.py:122-123), y el
 * registro de un vehículo no los exige.
 */
export const vehiculoRespuestaSinAnioNiKilometraje = {
    vehiculo_id: 13,
    cliente_id: 7,
    patente: 'CD5678',
    marca: 'Hyundai',
    modelo: 'Accent',
    anio: null,
    kilometraje: null,
};

/** Ejemplo real de gateway/contratos/ordenes.py:20 (_EJEMPLO_RESPUESTA). */
export const ordenRespuestaReal = {
    orden_id: 31,
    vehiculo_id: 12,
    ingreso_id: 18,
    estado_codigo: 1,
    mecanico_actual_id: null,
    creado_por_id: 99,
    creado_en: '2026-09-28T10:30:00-03:00',
    actualizado_en: '2026-09-28T10:30:00-03:00',
};

/** La misma orden una vez asignada a un mecánico. */
export const ordenRespuestaConMecanico = {
    ...ordenRespuestaReal,
    estado_codigo: 5,
    mecanico_actual_id: 50,
    actualizado_en: '2026-09-28T15:00:00-03:00',
};

/** Ejemplo real de gateway/contratos/ordenes.py:36 (_EJEMPLO_HISTORIAL). */
export const historialEstadoReal = {
    historial_id: 41,
    orden_id: 31,
    estado_anterior: 1,
    estado_nuevo: 2,
    actor_usuario_id: 50,
    origen: 'usuario' as const,
    fecha_hora: '2026-09-28T11:00:00-03:00',
    observacion: 'Inicia evaluación técnica',
};

/**
 * Registro de la transición de creación: la base exige coherencia entre el
 * origen y el actor (`origen = 'usuario' → actor no nulo`,
 * `origen = 'sistema' → actor nulo` en
 * ms2_taller/models/historial_estado.py:64-68), así que aquí los tres campos
 * opcionales llegan en null.
 */
export const historialEstadoDeCreacion = {
    historial_id: 40,
    orden_id: 31,
    estado_anterior: null,
    estado_nuevo: 1,
    actor_usuario_id: null,
    origen: 'sistema' as const,
    fecha_hora: '2026-09-28T10:30:00-03:00',
    observacion: null,
};

/** Ejemplo real de gateway/contratos/auth.py:37 (_EJEMPLO_TOKEN). */
export const tokenRespuestaReal = {
    access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3In0.firma',
    token_type: 'bearer',
    user: {
        id: 7,
        email: 'ana@correo.cl',
        full_name: 'Ana Pérez',
        roles: ['cliente'],
        is_active: true,
    },
};

/** Cuerpo real de GET /auth/me para un mecánico. */
export const usuarioRespuestaReal = {
    id: 42,
    email: 'mecanico@correo.cl',
    full_name: 'Martín Herrera',
    roles: ['mecanico'],
    is_active: true,
};

/**
 * El campo `roles` es una lista en el contrato (gateway/contratos/auth.py:105),
 * así que puede traer más de un rol. La app toma el primero; se fija con un test
 * para que el comportamiento no cambie por accidente.
 */
export const usuarioConDosRoles = {
    ...usuarioRespuestaReal,
    roles: ['mecanico', 'administrador'],
};

// ---------------------------------------------------------------------------
// Errores
// ---------------------------------------------------------------------------

/**
 * Cuerpo de error generado por la propia Gateway (gateway/esquemas.py:20):
 * `detail` es un string legible y `error` trae el código del catálogo, el
 * estado, la ruta y el request_id, que además viaja en la cabecera
 * `X-Request-ID` (gateway/errores.py:113).
 */
export function errorGateway(
    detail: string,
    codigo: string,
    estado: number,
    ruta = '/api/vehiculos'
) {
    return {
        detail,
        error: {
            codigo,
            estado,
            ruta,
            request_id: '9f1c2b3a-4d5e-6f70-8192-a3b4c5d6e7f8',
        },
    };
}

// Los siete códigos del catálogo de gateway/errores.py:31-39, con los mensajes
// literales de gateway/errores.py:53-66.
export const rutaNoEncontrada = errorGateway('Ruta no encontrada', 'RUTA_NO_ENCONTRADA', 404, '/api/vehiculos/999');
export const metodoNoPermitido = errorGateway('Método no permitido', 'METODO_NO_PERMITIDO', 405, '/api/vehiculos');
export const servicioInalcanzable = errorGateway(
    'El servicio no está disponible. Intente más tarde.',
    'MICROSERVICIO_INALCANZABLE',
    502,
    '/api/ordenes'
);
export const gatewaySaturada = errorGateway(
    'La Gateway está ocupada. Intente más tarde.',
    'GATEWAY_SATURADA',
    503,
    '/api/ordenes'
);
export const tiempoAgotado = errorGateway(
    'El servicio tardó demasiado en responder. Intente más tarde.',
    'TIEMPO_AGOTADO',
    504,
    '/api/vehiculos'
);
export const errorInternoGateway = errorGateway(
    'Ocurrió un error inesperado en la Gateway.',
    'ERROR_INTERNO',
    500,
    '/api/vehiculos'
);
// Una excepción no controlada en MS2: la Gateway normaliza el "Internal Server
// Error" de texto plano a este cuerpo (gateway/errores.py:66).
export const errorMicroServicio = errorGateway(
    'El servicio respondió con un error inesperado.',
    'ERROR_MICROSERVICIO',
    500,
    '/api/ordenes'
);

/**
 * Errores de los microservicios pasan tal cual por el proxy: llegan solo con
 * `detail` en string, sin el bloque `error`.
 */
export const patenteDuplicada = { detail: 'La patente ya está registrada' };
export const correoYaRegistrado = { detail: 'El correo ya está registrado' };
export const credencialesInvalidas = { detail: 'Correo o contraseña incorrectos' };
export const tokenInvalido = { detail: 'Token inválido o expirado' };
export const sinPermiso = { detail: 'No tienes permiso para realizar esta operación' };
/** Transición pedida a un estado fuera del catálogo (ms2_taller/routers/ordenes.py). */
export const estadoDesconocido = { detail: 'Estado de destino desconocido: 999' };
/** Límite de bcrypt, que se mide en bytes y no en caracteres (ms1_auth/security/passwords.py). */
export const contrasenaDemasiadoLarga = { detail: 'La contraseña no puede superar 72 bytes' };
/** 500 manejado por la ruta de MS2: llega con `detail` y sin bloque `error`. */
export const consultaVehiculosFallida = { detail: 'No fue posible consultar los vehículos' };
export const consultaOrdenesFallida = { detail: 'No fue posible consultar las órdenes' };

// --- Cambios de estado de una orden (PATCH /api/ordenes/{id}/estado) ---
// Los cinco literales que el frontend puede recibir al avanzar un estado. La
// autorización se valida antes que la transición (ms2_taller/services/ordenes.py:357
// antes de la 363), así que una orden reasignada devuelve 403 y no 409.

/**
 * 409 de `validar_transicion` cuando el par no está en la tabla
 * (ms2_taller/domain/transiciones_orden.py:158-161). El ejemplo es el que el
 * propio backend documenta en shared/openapi_ordenes.py:271-279.
 */
export const transicionNoPermitida = {
    detail: 'Transición no permitida: Recibido -> En reparación',
};
/**
 * 409 de `validar_estado_no_terminal` para los estados 7 y 8
 * (transiciones_orden.py:164-172).
 */
export const estadoTerminalNoTransicionable = {
    detail: 'El estado Entregado es terminal y no admite transiciones',
};
/**
 * 403 de `OrdenEstadoNoAutorizadoError`: el token es de un mecánico distinto al
 * `mecanico_actual_id` de la orden (ms2_taller/services/ordenes.py:357-360).
 */
export const sinPermisoCambiarEstado = {
    detail: 'No tienes permiso para cambiar el estado de esta orden',
};
/** 404 de la ruta de MS2 cuando la orden no existe. */
export const ordenNoEncontrada = { detail: 'Orden no encontrada' };
/**
 * 422 de validación de FastAPI sobre `CambioEstadoSolicitud`
 * (ms2_taller/schemas/orden.py:42-50). El modelo tiene `extra="forbid"`, así que
 * enviar `orden_id` o `actor_usuario_id` desde el frontend lo rechazaría.
 */
export const cambioEstadoBodyInvalido = {
    detail: [
        {
            loc: ['body', 'estado_destino'],
            msg: 'Input should be greater than 0',
            type: 'greater_than',
        },
    ],
};

/** 422 de validación de FastAPI: `detail` como lista de { loc, msg, type }. */
export const validacionPydantic = {
    detail: [
        {
            loc: ['body', 'patente'],
            msg: 'String should have at least 1 character',
            type: 'string_too_short',
        },
        {
            loc: ['body', 'anio'],
            msg: 'Input should be a valid integer',
            type: 'int_parsing',
        },
    ],
};

/**
 * El 422 que el backend devuelve si `marca` o `modelo` superan los 60
 * caracteres que declara el contrato (gateway/contratos/vehiculos.py:52-63 y
 * ms2_taller/schemas/vehiculo.py:20-21). Se conserva como prueba de por qué el
 * formulario valida ese mismo tope: sin él, la UI aceptaba el texto largo y el
 * servidor lo rechazaba.
 */
export const textoVehiculoDemasiadoLargo = {
    detail: [
        {
            loc: ['body', 'marca'],
            msg: 'String should have at most 60 characters',
            type: 'string_too_long',
        },
    ],
};

// ---------------------------------------------------------------------------
// Errores con forma de Axios
// ---------------------------------------------------------------------------

/** Request id de ejemplo para las cabeceras de la Gateway. */
export const REQUEST_ID = '9f1c2b3a-4d5e-6f70-8192-a3b4c5d6e7f8';

/**
 * Error con la forma que produce Axios, que es la que reciben `getApiErrorMessage`
 * e `isOfflineError`. `sinRespuesta` modela un fallo de transporte, donde no
 * llegó ninguna respuesta.
 */
export function errorAxios(status: number, data: unknown, headers: Record<string, string> = {}) {
    return { isAxiosError: true, response: { status, data, headers } };
}

/** Fallo de transporte: hay Axios pero no hay respuesta HTTP. */
export const sinRespuesta = { isAxiosError: true };
