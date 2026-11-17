import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/infrastructure/config/apiClient';
import { LIMITE_PAGINA, obtenerTodasLasPaginas } from './paginacion';

vi.mock('@/infrastructure/config/apiClient', () => ({
    default: {
        get: vi.fn(),
    },
}));

interface Fila {
    id: number;
}

function filas(desde: number, cantidad: number): Fila[] {
    return Array.from({ length: cantidad }, (_, indice) => ({ id: desde + indice }));
}

describe('obtenerTodasLasPaginas', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('recorre todas las páginas usando X-Total-Count', async () => {
        vi.mocked(apiClient.get)
            .mockResolvedValueOnce({
                data: filas(0, LIMITE_PAGINA),
                headers: { 'x-total-count': String(LIMITE_PAGINA + 5) },
            })
            .mockResolvedValueOnce({
                data: filas(LIMITE_PAGINA, 5),
                headers: { 'x-total-count': String(LIMITE_PAGINA + 5) },
            });

        const resultado = await obtenerTodasLasPaginas<Fila>('/recurso');

        expect(apiClient.get).toHaveBeenCalledTimes(2);
        expect(apiClient.get).toHaveBeenNthCalledWith(1, '/recurso', {
            params: { limite: LIMITE_PAGINA, desde: 0 },
        });
        expect(apiClient.get).toHaveBeenNthCalledWith(2, '/recurso', {
            params: { limite: LIMITE_PAGINA, desde: LIMITE_PAGINA },
        });
        expect(resultado).toHaveLength(LIMITE_PAGINA + 5);
    });

    it('conserva los filtros recibidos en cada página', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
            data: filas(0, 2),
            headers: { 'x-total-count': '2' },
        });

        await obtenerTodasLasPaginas<Fila>('/evidencias', { orden_id: '31' });

        expect(apiClient.get).toHaveBeenCalledWith('/evidencias', {
            params: { orden_id: '31', limite: LIMITE_PAGINA, desde: 0 },
        });
    });

    it('sin X-Total-Count se detiene al recibir una página incompleta', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: filas(0, 3) });

        const resultado = await obtenerTodasLasPaginas<Fila>('/recurso');

        expect(apiClient.get).toHaveBeenCalledTimes(1);
        expect(resultado).toHaveLength(3);
    });

    it('se detiene cuando una página llega vacía', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: [] });

        const resultado = await obtenerTodasLasPaginas<Fila>('/recurso');

        expect(apiClient.get).toHaveBeenCalledTimes(1);
        expect(resultado).toEqual([]);
    });
});
