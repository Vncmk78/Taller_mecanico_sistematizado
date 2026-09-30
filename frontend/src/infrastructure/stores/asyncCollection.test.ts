import { beforeEach, describe, expect, it, vi } from 'vitest';
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
}

let state: TestState;
const set = (patch: Partial<TestState> | ((s: TestState) => Partial<TestState>)) => {
    state = { ...state, ...(typeof patch === 'function' ? patch(state) : patch) };
};
const getItems = () => state.items;
const upsert = (s: TestState, item: TestItem) => ({ items: upsertById(s.items, item) });

describe('asyncCollection: helpers de colección asíncrona', () => {
    beforeEach(() => {
        state = { items: [], status: 'idle', error: null, isOffline: false };
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
            expect(result.item?.id).toBe('1');
            expect(state.isOffline).toBe(true);
            expect(state.error).not.toBeNull();
        });
    });
});