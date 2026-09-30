import { describe, expect, it } from 'vitest';
import { getApiErrorMessage, isConflictError, isNotFoundError, isOfflineError } from './errors';

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
