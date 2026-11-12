import { describe, expect, it, vi } from 'vitest';
import { QueryClientProvider, useQuery } from '@tanstack/react-query';
import { render, waitFor } from '@testing-library/react';
import { createQueryClient, shouldRetryQuery } from './queryClient';

/** Un AxiosError plano para el predicado: axios.isAxiosError solo mira `isAxiosError`. */
function errorAxios(status?: number): unknown {
    return Object.assign(new Error('Request failed with status code ' + (status ?? 'sin respuesta')), {
        isAxiosError: true,
        ...(status === undefined ? {} : { response: { status, data: {} } }),
    });
}

describe('shouldRetryQuery: reintento solo ante fallos transitorios', () => {
    it('reintenta errores sin respuesta (red caída / timeout)', () => {
        expect(shouldRetryQuery(0, errorAxios())).toBe(true);
    });

    it('reintenta 5xx (microservicio caído, Gateway saturada)', () => {
        expect(shouldRetryQuery(0, errorAxios(500))).toBe(true);
        expect(shouldRetryQuery(1, errorAxios(502))).toBe(true);
        expect(shouldRetryQuery(1, errorAxios(503))).toBe(true);
    });

    it('no reintenta 4xx deterministas: repetirlos solo duplica el ruido', () => {
        for (const status of [400, 401, 403, 404, 409, 422]) {
            expect(shouldRetryQuery(0, errorAxios(status))).toBe(false);
        }
    });

    it('no reintenta errores que no vienen de axios', () => {
        expect(shouldRetryQuery(0, new Error('boom'))).toBe(false);
    });

    it('deja de reintentar al alcanzar el tope', () => {
        expect(shouldRetryQuery(2, errorAxios(503))).toBe(false);
        expect(shouldRetryQuery(3, errorAxios(503))).toBe(false);
    });
});

describe('createQueryClient', () => {
    it('usa el reintento inteligente como default de las consultas', () => {
        const client = createQueryClient();
        expect(client.getDefaultOptions().queries?.retry).toBe(shouldRetryQuery);
    });

    it('loggea el fallo con queryKey, mensaje y request-id, sin volcar el token', async () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        // Un AxiosError lleva `config.headers.Authorization` dentro. Volcar el
        // objeto completo en la consola del navegador mostraría el token de
        // acceso al expandirlo, que es lo que se ve al compartir pantalla.
        const token = 'eyJhbGciOiJIUzI1NiJ9.token-falso.firma-falsa';
        const error = Object.assign(
            new Error('Request failed with status code 503'),
            {
                isAxiosError: true,
                config: { headers: { Authorization: `Bearer ${token}` } },
                response: {
                    status: 503,
                    data: { error: { codigo: 'GATEWAY_SATURADA', request_id: 'req-abc-123' } },
                    headers: {},
                },
            }
        );

        function Sonda() {
            useQuery({ queryKey: ['avisos'], queryFn: () => Promise.reject(error), retry: false });
            return null;
        }

        const client = createQueryClient();
        render(
            <QueryClientProvider client={client}>
                <Sonda />
            </QueryClientProvider>
        );

        await waitFor(() => {
            const propias = consoleSpy.mock.calls.filter(
                (argumentos) => argumentos[0] === '[React Query] Fallo de consulta'
            );
            expect(propias).toHaveLength(1);
            const argumentos = propias[0].slice(1);
            const texto = argumentos.map(String).join(' ');
            expect(texto).toContain('queryKey=["avisos"]');
            expect(texto).toContain('request-id=req-abc-123');
            expect(texto).not.toContain(token);
            // Solo se pasan cadenas armadas con helpers seguros: el objeto
            // `error` completo (con config.headers.Authorization) nunca llega
            // a la consola del navegador.
            expect(argumentos.every((argumento) => typeof argumento === 'string')).toBe(true);
        });
        consoleSpy.mockRestore();
    });
});
