import { beforeEach, describe, expect, it } from 'vitest';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import { useOrderHistoryStore } from './useOrderHistoryStore';

const h1: OrderHistoryEntry = {
    id: 'h1',
    ordenId: '101',
    estadoAnteriorCodigo: null,
    estadoNuevoCodigo: 1,
    actorUsuarioId: null,
    origen: 'sistema',
    fecha: '2026-09-01T10:00:00',
    observacion: 'ingreso',
};

const h1b: OrderHistoryEntry = {
    id: 'h1b',
    ordenId: '101',
    estadoAnteriorCodigo: 1,
    estadoNuevoCodigo: 5,
    actorUsuarioId: 1,
    origen: 'usuario',
    fecha: '2026-09-02T10:00:00',
    observacion: 'avance',
    usuarioNombre: 'Martín Herrera',
};

const h2: OrderHistoryEntry = {
    id: 'h2',
    ordenId: '102',
    estadoAnteriorCodigo: null,
    estadoNuevoCodigo: 1,
    actorUsuarioId: null,
    origen: 'sistema',
    fecha: '2026-09-03T10:00:00',
    observacion: 'ingreso',
};

describe('useOrderHistoryStore: caché del historial por orden', () => {
    beforeEach(() => {
        useOrderHistoryStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
    });

    it('reemplaza solo el historial de la orden consultada', async () => {
        useOrderHistoryStore.setState({ entries: [h1, h2] });

        await useOrderHistoryStore.getState().fetchOrderHistory('101', async () => [h1b]);

        const state = useOrderHistoryStore.getState();
        expect(state.entries.map((e) => e.id)).toEqual(['h2', 'h1b']);
        expect(state.isOffline).toBe(false);
        expect(state.status).toBe('success');
    });

    it('ante error queda offline y conserva la caché', async () => {
        useOrderHistoryStore.setState({ entries: [h2] });

        await useOrderHistoryStore.getState().fetchOrderHistory('101', async () => {
            throw new Error('network');
        });

        const state = useOrderHistoryStore.getState();
        expect(state.isOffline).toBe(true);
        expect(state.status).toBe('error');
        expect(state.entries.map((e) => e.id)).toEqual(['h2']);
    });
});