import { describe, expect, it } from 'vitest';
import type { Order } from '@/domain/entities/Order';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { filterOrdersByMechanic, filterVehiclesByOrders } from '@/presentation/utils/mechanicScope';

function orden(id: string, vehicleId: string, mecanicoActualId: string | null): Order {
    return {
        id,
        vehicleId,
        ingresoId: Number(id),
        estadoCodigo: 5,
        mecanicoActualId,
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: '2026-09-05T16:30:00',
    };
}

function vehiculo(id: string): Vehicle {
    return { id, patent: `PT-${id}`, brand: 'Ford', model: 'Fiesta', year: 2018, mileage: 1000, clientId: 'c1' };
}

describe('filterOrdersByMechanic', () => {
    it('conserva solo las órdenes cuyo mecanicoActualId coincide con la sesión', () => {
        const orders = [orden('1', '10', 'm1'), orden('2', '20', 'm2'), orden('3', '30', 'm1')];

        expect(filterOrdersByMechanic(orders, 'm1').map((o) => o.id)).toEqual(['1', '3']);
    });

    it('descarta las órdenes sin mecánico asignado', () => {
        const orders = [orden('1', '10', 'm1'), orden('2', '20', null)];

        expect(filterOrdersByMechanic(orders, 'm1').map((o) => o.id)).toEqual(['1']);
    });

    it('no muestra nada cuando no hay identidad de sesión', () => {
        const orders = [orden('1', '10', 'm1')];

        expect(filterOrdersByMechanic(orders, null)).toEqual([]);
        expect(filterOrdersByMechanic(orders, undefined)).toEqual([]);
    });
});

describe('filterVehiclesByOrders', () => {
    it('conserva solo los vehículos referenciados por las órdenes entregadas', () => {
        const vehicles = [vehiculo('10'), vehiculo('20'), vehiculo('30')];
        const orders = [orden('1', '10', 'm1'), orden('2', '20', 'm1')];

        expect(filterVehiclesByOrders(vehicles, orders).map((v) => v.id)).toEqual(['10', '20']);
    });

    it('no repite vehículos cuando varias órdenes comparten el mismo', () => {
        const vehicles = [vehiculo('10')];
        const orders = [orden('1', '10', 'm1'), orden('2', '10', 'm1')];

        expect(filterVehiclesByOrders(vehicles, orders).map((v) => v.id)).toEqual(['10']);
    });

    it('descarta toda la caché cuando no hay órdenes', () => {
        expect(filterVehiclesByOrders([vehiculo('10')], [])).toEqual([]);
    });
});