import { beforeEach, describe, expect, it, vi } from 'vitest';
import { errorAxios, gatewaySaturada } from '@/infrastructure/mocks/payloads.reales';
import type { FetchStatus } from './asyncCollection';
import {
    fetchCollection,
    fetchItemById,
    mergeById,
    replaceWhere,
    upsertById,
} from './asyncCollection';

interface TestItem {
    id: string;
    name: string;
}

interface TestState {
    items: TestItem[];
    status: FetchStatus;
    error: string | null;
    isOffline: boolean;
    requestId: string | null;
}

let state: TestState;
const set = (patch: Partial<TestState> | ((s: TestState) => Partial<TestState>)) => {
    state = { ...state, ...(typeof patch === 'function' ? patch(state) : patch) };
};
const getItems = () => state.items;
const upsert = (s: TestState, item: TestItem) => ({ items: upsertById(s.items, item) });

describe('asyncCollection: helpers de colección asíncrona', () => {
    beforeEach(() => {
        state = { items: [], status: 'idle', error: null, isOffline: false, requestId: null };
        vi.clearAllMocks();
    });

    describe('mergeById / upsertById / replaceWhere', () => {
        it('mergeById combina por id sin duplicar y actualiza los existentes', () => {
            const result = mergeById(
                [{ id: '1', name: 'a' }, { id: '2', name: 'b' }],
                [{ id: '2', name: 'b2' }, { id: '3', name: 'c' }]
            );
            expect(result.map((i) => i.id)).toEqual(['1', '2', '3']);
            expect(result.find((i) => i.id === '2')?.name).toBe('b2');
        });

        it('upsertById actualiza el existente y agrega el nuevo', () => {
            const updated = upsertById([{ id: '1', name: 'a' }], { id: '1', name: 'a2' });
            expect(updated).toHaveLength(1);
            expect(updated[0].name).toBe('a2');

            const appended = upsertById([{ id: '1', name: 'a' }], { id: '2', name: 'b' });
            expect(appended.map((i) => i.id)).toEqual(['1', '2']);
        });

        it('replaceWhere reemplaza solo los que calzan con la clave', () => {
            const result = replaceWhere(
                [{ id: 'h1', ordenId: '101' }, { id: 'h2', ordenId: '102' }],
                'ordenId',
                '101',
                [{ id: 'h3', ordenId: '101' }]
            );
            expect(result.map((i) => i.id)).toEqual(['h2', 'h3']);
        });
    });

    describe('fetchCollection', () => {
        it('carga, integra con la caché y marca success', async () => {
            state.items = [{ id: '1', name: 'a' }];

            await fetchCollection<TestItem, TestState>(
                async () => [{ id: '1', name: 'a2' }, { id: '2', name: 'b' }],
                set,
                (s, fetched) => ({ items: mergeById(s.items, fetched) })
            );

            expect(state.status).toBe('success');
            expect(state.isOffline).toBe(false);
            expect(state.error).toBeNull();
            expect(state.items.map((i) => i.id)).toEqual(['1', '2']);
            expect(state.items.find((i) => i.id === '1')?.name).toBe('a2');
        });

        it('marca loading durante la petición', async () => {
            let resolveLoader: (value: TestItem[]) => void = () => {};
            const loader = vi.fn(
                () => new Promise<TestItem[]>((resolve) => {
                    resolveLoader = resolve;
                })
            );

            const promise = fetchCollection<TestItem, TestState>(
                loader,
                set,
                (_s, fetched) => ({ items: fetched })
            );

            expect(state.status).toBe('loading');
            resolveLoader([]);
            await promise;
            expect(state.status).toBe('success');
        });

        it('ante error queda offline y conserva la caché', async () => {
            state.items = [{ id: '1', name: 'a' }];

            await fetchCollection<TestItem, TestState>(
                async () => {
                    throw new Error('network');
                },
                set,
                (_s, fetched) => ({ items: fetched })
            );

            expect(state.status).toBe('error');
            expect(state.isOffline).toBe(true);
            expect(state.error).not.toBeNull();
            expect(state.items.map((i) => i.id)).toEqual(['1']);
        });

        it('un error del servidor no se marca offline y conserva la caché', async () => {
            state.items = [{ id: '1', name: 'a' }];
            const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

            await fetchCollection<TestItem, TestState>(
                async () => {
                    throw axios500;
                },
                set,
                (_s, fetched) => ({ items: fetched })
            );

            expect(state.status).toBe('error');
            expect(state.isOffline).toBe(false);
            expect(state.error).toMatch(/El servidor tuvo un problema/);
            expect(state.items.map((i) => i.id)).toEqual(['1']);
        });

        it('un 503 (servicio no disponible) sí se marca offline', async () => {
            const axios503 = { isAxiosError: true, response: { status: 503, data: {} } };

            await fetchCollection<TestItem, TestState>(
                async () => {
                    throw axios503;
                },
                set,
                (_s, fetched) => ({ items: fetched })
            );

            expect(state.status).toBe('error');
            expect(state.isOffline).toBe(true);
        });

        it('guarda el request_id de la Gateway y el mensaje real del 503', async () => {
            // Cuerpo real de gateway/errores.py: el mensaje del backend debe
            // llegar a la vista y la referencia permitir rastrearlo en los logs.
            await fetchCollection<TestItem, TestState>(
                async () => {
                    throw errorAxios(503, gatewaySaturada);
                },
                set,
                (_s, fetched) => ({ items: fetched })
            );

            expect(state.error).toBe('La Gateway está ocupada. Intente más tarde.');
            expect(state.requestId).toBe('9f1c2b3a-4d5e-6f70-8192-a3b4c5d6e7f8');
        });

        it('deja el request_id en null cuando el error no lo trae', async () => {
            await fetchCollection<TestItem, TestState>(
                async () => {
                    throw errorAxios(500, { detail: 'No fue posible consultar los vehículos' });
                },
                set,
                (_s, fetched) => ({ items: fetched })
            );

            expect(state.error).toBe('No fue posible consultar los vehículos');
            expect(state.requestId).toBeNull();
        });

        it('limpia el request_id de un fallo anterior al reintentar con éxito', async () => {
            state = { items: [], status: 'error', error: 'La Gateway está ocupada.', isOffline: true, requestId: 'req-1' };

            await fetchCollection<TestItem, TestState>(async () => [{ id: '1', name: 'a' }], set, (_s, fetched) => ({
                items: fetched,
            }));

            expect(state.status).toBe('success');
            expect(state.requestId).toBeNull();
        });

        it('al reintentar limpia el estado offline anterior', async () => {
            state = { items: [], status: 'error', error: 'No se pudo conectar', isOffline: true, requestId: null };
            let resolveLoader: (value: TestItem[]) => void = () => {};

            const promise = fetchCollection<TestItem, TestState>(
                () => new Promise<TestItem[]>((resolve) => { resolveLoader = resolve; }),
                set,
                (_s, fetched) => ({ items: fetched })
            );

            // Durante el reintento no se muestra el banner offline junto al skeleton.
            expect(state.status).toBe('loading');
            expect(state.isOffline).toBe(false);
            expect(state.error).toBeNull();

            resolveLoader([]);
            await promise;
        });
    });

    describe('fetchItemById', () => {
        it('hace upsert y devuelve la entidad sin notFound', async () => {
            state.items = [{ id: '1', name: 'a' }];

            const result = await fetchItemById<TestItem, TestState>(
                '1',
                async () => ({ id: '1', name: 'a2' }),
                set,
                getItems,
                upsert
            );

            expect(result.notFound).toBe(false);
            expect(result.failed).toBe(false);
            expect(result.item?.name).toBe('a2');
            expect(state.items.find((i) => i.id === '1')?.name).toBe('a2');
            expect(state.isOffline).toBe(false);
        });

        it('con 404 marca notFound sin tocar la caché', async () => {
            state.items = [{ id: '1', name: 'a' }];
            const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };

            const result = await fetchItemById<TestItem, TestState>(
                '9',
                async () => {
                    throw axios404;
                },
                set,
                getItems,
                upsert
            );

            expect(result.notFound).toBe(true);
            expect(result.failed).toBe(false);
            expect(result.item).toBeNull();
            expect(state.items.map((i) => i.id)).toEqual(['1']);
            expect(state.isOffline).toBe(false);
        });

        it('con error de red usa la caché local y marca offline', async () => {
            state.items = [{ id: '1', name: 'a' }];

            const result = await fetchItemById<TestItem, TestState>(
                '1',
                async () => {
                    throw new Error('network');
                },
                set,
                getItems,
                upsert
            );

            expect(result.notFound).toBe(false);
            expect(result.failed).toBe(false);
            expect(result.item?.id).toBe('1');
            expect(state.isOffline).toBe(true);
            expect(state.error).not.toBeNull();
        });

        it('sin caché local devuelve failed en vez de un falso notFound', async () => {
            state.items = [];

            const result = await fetchItemById<TestItem, TestState>(
                '9',
                async () => {
                    throw new Error('network');
                },
                set,
                getItems,
                upsert
            );

            // Un corte de red no puede presentarse como "no encontrado".
            expect(result.notFound).toBe(false);
            expect(result.failed).toBe(true);
            expect(result.item).toBeNull();
        });

        it('un error del servidor con caché local no se marca offline', async () => {
            state.items = [{ id: '1', name: 'a' }];
            const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

            const result = await fetchItemById<TestItem, TestState>(
                '1',
                async () => {
                    throw axios500;
                },
                set,
                getItems,
                upsert
            );

            expect(result.item?.id).toBe('1');
            expect(result.failed).toBe(false);
            expect(state.isOffline).toBe(false);
            expect(state.error).toMatch(/El servidor tuvo un problema/);
        });
    });
});