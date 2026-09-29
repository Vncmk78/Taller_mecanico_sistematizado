import { beforeEach, describe, expect, it } from 'vitest';
import type { Order } from '@/domain/entities/Order';
import { useOrderStore } from './useOrderStore';

const base: Order = {
    id: '1',
    vehicleId: '1',
    ingresoId: 1,
    estadoCodigo: 1,
    mecanicoActualId: null,
    creadoPorId: 'u1',
    creadoEn: '2026-09-01T10:00:00',
    actualizadoEn: '2026-09-01T10:00:00',
};

const o1b: Order = { ...base, estadoCodigo: 5 };
const o2: Order = { ...base, id: '2', ingresoId: 2 };

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };

describe('useOrderStore: caché y estados del listado/detalle de órdenes', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
    });

    it('fetchOrders exitoso marca success y no queda offline', async () => {
        await useOrderStore.getState().fetchOrders(async () => [base, o2]);

        const state = useOrderStore.getState();
        expect(state.status).toBe('success');
        expect(state.isOffline).toBe(false);
        expect(state.orders.map((o) => o.id)).toEqual(['1', '2']);
    });

    it('fetchOrders hace merge por id sin pisar la caché local', async () => {
        useOrderStore.setState({ orders: [base] });

        await useOrderStore.getState().fetchOrders(async () => [o1b, o2]);

        const state = useOrderStore.getState();
        expect(state.orders).toHaveLength(2);
        expect(state.orders.find((o) => o.id === '1')?.estadoCodigo).toBe(5);
    });

    it('fetchOrders ante error queda offline y conserva la caché', async () => {
        useOrderStore.setState({ orders: [base] });

        await useOrderStore.getState().fetchOrders(async () => {
            throw new Error('network');
        });

        const state = useOrderStore.getState();
        expect(state.status).toBe('error');
        expect(state.isOffline).toBe(true);
        expect(state.orders.map((o) => o.id)).toEqual(['1']);
    });

    it('fetchOrderById hace upsert de la orden', async () => {
        useOrderStore.setState({ orders: [base] });

        const first = await useOrderStore.getState().fetchOrderById('1', async () => o1b);
        expect(first.notFound).toBe(false);
        expect(useOrderStore.getState().orders.find((o) => o.id === '1')?.estadoCodigo).toBe(5);

        const second = await useOrderStore.getState().fetchOrderById('2', async () => o2);
        expect(second.notFound).toBe(false);
        expect(useOrderStore.getState().orders.map((o) => o.id)).toEqual(['1', '2']);
    });

    it('fetchOrderById con 404 marca notFound', async () => {
        const result = await useOrderStore.getState().fetchOrderById('9', async () => {
            throw axios404;
        });

        expect(result.notFound).toBe(true);
        expect(result.order).toBeNull();
    });

    it('fetchOrderById con error de red usa la caché local sin marcar notFound', async () => {
        useOrderStore.setState({ orders: [{ ...base, estadoCodigo: 5 }] });

        const result = await useOrderStore.getState().fetchOrderById('1', async () => {
            throw new Error('network');
        });

        expect(result.notFound).toBe(false);
        expect(result.order?.id).toBe('1');
        expect(useOrderStore.getState().isOffline).toBe(true);
        expect(useOrderStore.getState().error).not.toBeNull();
    });
});