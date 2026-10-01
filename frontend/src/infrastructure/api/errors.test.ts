import { describe, expect, it } from 'vitest';
import {
    getApiErrorCode,
    getApiErrorMessage,
    getApiErrorRequestId,
    isConflictError,
    isNotFoundError,
    isOfflineError,
} from './errors';
import {
    contrasenaDemasiadoLarga,
    credencialesInvalidas,
    errorAxios,
    errorGateway,
    errorInternoGateway,
    errorMicroServicio,
    estadoDesconocido,
    gatewaySaturada,
    metodoNoPermitido,
    patenteDuplicada,
    correoYaRegistrado,
    REQUEST_ID,
    rutaNoEncontrada,
    servicioInalcanzable,
    sinPermiso,
    sinRespuesta as sinRespuestaReal,
    tiempoAgotado,
    textoVehiculoDemasiadoLargo,
    tokenInvalido,
    validacionPydantic,
} from '@/infrastructure/mocks/payloads.reales';

// Errores simulados con la misma forma que produce Axios, que es lo que
// isOfflineError y el resto de helpers reciben en la práctica.
const sinRespuesta = { isAxiosError: true };
const http = (status: number, data: unknown = {}) => ({ isAxiosError: true, response: { status, data } });

describe('isOfflineError: distingue fallo de transporte de error del servidor', () => {
    it('trata como offline un error que no es de Axios (transporte/inesperado)', () => {
        expect(isOfflineError(new Error('boom'))).toBe(true);
        expect(isOfflineError('no soy un error')).toBe(true);
    });

    it('trata como offline un error Axios sin respuesta HTTP', () => {
        expect(isOfflineError(sinRespuesta)).toBe(true);
    });

    it('trata como offline un servicio no disponible (502/503/504)', () => {
        expect(isOfflineError(http(502))).toBe(true);
        expect(isOfflineError(http(503))).toBe(true);
        expect(isOfflineError(http(504))).toBe(true);
    });

    it('no trata como offline los errores del servidor ni los de negocio', () => {
        expect(isOfflineError(http(500))).toBe(false);
        expect(isOfflineError(http(401))).toBe(false);
        expect(isOfflineError(http(403))).toBe(false);
        expect(isOfflineError(http(404))).toBe(false);
        expect(isOfflineError(http(409))).toBe(false);
        expect(isOfflineError(http(422))).toBe(false);
    });
});

describe('getApiErrorMessage: mensajes por tipo de fallo', () => {
    it('usa el mensaje de conexión cuando no hubo respuesta', () => {
        expect(getApiErrorMessage(sinRespuesta)).toMatch(/No se pudo conectar con el servidor/);
    });

    it('prefiere el detail del backend cuando es un string', () => {
        expect(getApiErrorMessage(http(422, { detail: 'Estado de destino desconocido: 999' }))).toBe(
            'Estado de destino desconocido: 999'
        );
    });

    it('usa el primer msg cuando detail es la lista de validación de FastAPI', () => {
        const error = http(422, { detail: [{ msg: 'placa debe tener entre 5 y 10 caracteres', loc: ['body'] }] });

        expect(getApiErrorMessage(error)).toBe('placa debe tener entre 5 y 10 caracteres');
    });

    it('traduce los status sin detail utilizable', () => {
        expect(getApiErrorMessage(http(404))).toBe('El recurso solicitado no fue encontrado.');
        expect(getApiErrorMessage(http(409))).toBe('Ya existe un registro con esos datos.');
        expect(getApiErrorMessage(http(500))).toMatch(/El servidor tuvo un problema/);
    });

    it('cae en el fallback ante errores que no son de Axios', () => {
        expect(getApiErrorMessage(new Error('boom'), 'No se pudo actualizar el estado.')).toBe(
            'No se pudo actualizar el estado.'
        );
    });
});

describe('isNotFoundError / isConflictError', () => {
    it('reconocen 404 y 409 respectivamente', () => {
        expect(isNotFoundError(http(404))).toBe(true);
        expect(isNotFoundError(http(409))).toBe(false);
        expect(isConflictError(http(409))).toBe(true);
        expect(isConflictError(http(404))).toBe(false);
    });
});

// A partir de aquí los cuerpos son literales del backend: el formato propio de
// la Gateway (gateway/esquemas.py) y los mensajes que emiten MS1 y MS2.
describe('getApiErrorMessage: catálogo real de errores de la Gateway', () => {
    it('usa el detail de cada código del catálogo, no el fallback por status', () => {
        expect(getApiErrorMessage(errorAxios(404, rutaNoEncontrada))).toBe('Ruta no encontrada');
        expect(getApiErrorMessage(errorAxios(405, metodoNoPermitido))).toBe('Método no permitido');
        expect(getApiErrorMessage(errorAxios(500, errorInternoGateway))).toBe(
            'Ocurrió un error inesperado en la Gateway.'
        );
        expect(getApiErrorMessage(errorAxios(500, errorMicroServicio))).toBe(
            'El servicio respondió con un error inesperado.'
        );
    });

    it('muestra el mensaje propio de 502, 503 y 504, que sigue siendo un fallo de transporte', () => {
        // Estos tres los marca la UI como "sin conexión" y muestran la caché
        // local, pero el texto que ve el usuario es el que escribió el backend,
        // no un mensaje genérico: así sabe si reintentar tiene sentido.
        const casos = [
            [502, servicioInalcanzable, 'El servicio no está disponible. Intente más tarde.'],
            [503, gatewaySaturada, 'La Gateway está ocupada. Intente más tarde.'],
            [504, tiempoAgotado, 'El servicio tardó demasiado en responder. Intente más tarde.'],
        ] as const;

        for (const [status, cuerpo, mensaje] of casos) {
            const error = errorAxios(status, cuerpo);
            expect(getApiErrorMessage(error)).toBe(mensaje);
            expect(isOfflineError(error)).toBe(true);
        }
    });

    it('no confunde el 500 de la Gateway con un fallo de transporte', () => {
        // Los 500 son errores del servidor: la vista muestra el estado de error
        // reintentable, no el aviso de "sin conexión".
        expect(isOfflineError(errorAxios(500, errorInternoGateway))).toBe(false);
        expect(isOfflineError(errorAxios(500, errorMicroServicio))).toBe(false);
    });
});

describe('getApiErrorMessage: mensajes reales de los microservicios', () => {
    it('muestra el literal de MS2 cuando la patente ya existe', () => {
        const error = errorAxios(409, patenteDuplicada);

        expect(getApiErrorMessage(error)).toBe('La patente ya está registrada');
        expect(isConflictError(error)).toBe(true);
    });

    it('muestra el literal de MS1 cuando el correo ya está registrado', () => {
        expect(getApiErrorMessage(errorAxios(409, correoYaRegistrado))).toBe('El correo ya está registrado');
    });

    it('distingue credenciales inválidas de token inválido o expirado', () => {
        expect(getApiErrorMessage(errorAxios(401, credencialesInvalidas))).toBe(
            'Correo o contraseña incorrectos'
        );
        expect(getApiErrorMessage(errorAxios(401, tokenInvalido))).toBe('Token inválido o expirado');
    });

    it('propaga el 403 de permisos con su mensaje propio', () => {
        expect(getApiErrorMessage(errorAxios(403, sinPermiso))).toBe(
            'No tienes permiso para realizar esta operación'
        );
    });

    it('usa el primer msg de la lista de validación de FastAPI', () => {
        expect(getApiErrorMessage(errorAxios(422, validacionPydantic))).toBe(
            'String should have at least 1 character'
        );
    });

    it('muestra el 422 de texto demasiado largo, que el formulario ahora evita', () => {
        // Es el rechazo que recibía el usuario si escribía más de 60 caracteres
        // en marca o modelo: el backend lo cortaba aunque la UI lo aceptara.
        expect(getApiErrorMessage(errorAxios(422, textoVehiculoDemasiadoLargo))).toBe(
            'String should have at most 60 characters'
        );
    });

    it('usa el detail en string de los 422 que no vienen como lista', () => {
        expect(getApiErrorMessage(errorAxios(422, estadoDesconocido))).toBe('Estado de destino desconocido: 999');
        expect(getApiErrorMessage(errorAxios(422, contrasenaDemasiadoLarga))).toBe(
            'La contraseña no puede superar 72 bytes'
        );
    });

    it('usa el detail del 500 manejado por MS2, que llega sin bloque error', () => {
        const cuerpo = { detail: 'No fue posible consultar los vehículos' };

        expect(getApiErrorMessage(errorAxios(500, cuerpo))).toBe('No fue posible consultar los vehículos');
    });
});

describe('getApiErrorRequestId / getApiErrorCode: rastreo de la petición', () => {
    it('lee el request_id del bloque error de la Gateway', () => {
        expect(getApiErrorRequestId(errorAxios(503, gatewaySaturada))).toBe(REQUEST_ID);
        expect(getApiErrorCode(errorAxios(503, gatewaySaturada))).toBe('GATEWAY_SATURADA');
    });

    it('cae en la cabecera X-Request-ID cuando el cuerpo no lo trae', () => {
        const error = errorAxios(500, { detail: 'Ocurrió un error inesperado en la Gateway.' }, {
            'x-request-id': 'abc-123',
        });

        expect(getApiErrorRequestId(error)).toBe('abc-123');
        expect(getApiErrorCode(error)).toBeNull();
    });

    it('no inventa una referencia en los errores que no la traen', () => {
        // Los errores que un microservicio emite pasan tal cual por el proxy:
        // no hay request_id que mostrar.
        expect(getApiErrorRequestId(errorAxios(409, patenteDuplicada))).toBeNull();
        expect(getApiErrorCode(errorAxios(409, patenteDuplicada))).toBeNull();
        // Sin respuesta HTTP tampoco hay nada que rastrear.
        expect(getApiErrorRequestId(sinRespuestaReal)).toBeNull();
        expect(getApiErrorCode(sinRespuestaReal)).toBeNull();
        expect(getApiErrorRequestId(new Error('boom'))).toBeNull();
    });

    it('ignora un request_id vacío en vez de mostrar una referencia en blanco', () => {
        const error = errorAxios(500, { detail: 'x', error: { request_id: '' } }, { 'x-request-id': '' });

        expect(getApiErrorRequestId(error)).toBeNull();
    });

    it('expone el código de cada fallo de la Gateway para clasificar sin parsear el mensaje', () => {
        expect(getApiErrorCode(errorAxios(404, rutaNoEncontrada))).toBe('RUTA_NO_ENCONTRADA');
        expect(getApiErrorCode(errorAxios(405, metodoNoPermitido))).toBe('METODO_NO_PERMITIDO');
        expect(getApiErrorCode(errorAxios(502, servicioInalcanzable))).toBe('MICROSERVICIO_INALCANZABLE');
        expect(getApiErrorCode(errorAxios(504, tiempoAgotado))).toBe('TIEMPO_AGOTADO');
        expect(getApiErrorCode(errorAxios(500, errorInternoGateway))).toBe('ERROR_INTERNO');
        expect(getApiErrorCode(errorAxios(500, errorMicroServicio))).toBe('ERROR_MICROSERVICIO');
        expect(getApiErrorCode(errorAxios(500, errorGateway('Fallo al reintentar.', 'ERROR_HTTP', 502)))).toBe(
            'ERROR_HTTP'
        );
    });
});
