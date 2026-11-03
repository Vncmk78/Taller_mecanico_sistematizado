import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { VehicleOrderHistoryPanel } from './VehicleOrderHistoryPanel';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: { getVehicleOrderHistory: vi.fn() },
}));

function crearOrden(id: number): Order {
    return {
        id: String(id),
        vehicleId: '12',
        ingresoId: id,
        estadoCodigo: 7,
        mecanicoActualId: null,
        creadoPorId: '99',
        creadoEn: '2026-09-19T15:00:00.000Z',
        actualizadoEn: '2026-09-20T10:00:00.000Z',
    };
}

function renderPanel() {
    return render(
        <MemoryRouter>
            <VehicleOrderHistoryPanel
                vehicleId="12"
                detailPathPrefix="/admin/ordenes"
                vehicleLabel="Toyota Yaris"
            />
        </MemoryRouter>
    );
}

describe('VehicleOrderHistoryPanel', () => {
    beforeEach(() => vi.clearAllMocks());

    it('navega por páginas y conserva el total y la ruta al detalle', async () => {
        vi.mocked(orderService.getVehicleOrderHistory)
            .mockResolvedValueOnce({
                items: Array.from({ length: 20 }, (_, index) => crearOrden(index + 1)),
                total: 21,
                limit: 20,
                offset: 0,
            })
            .mockResolvedValueOnce({
                items: [crearOrden(21)],
                total: 21,
                limit: 20,
                offset: 20,
            });

        renderPanel();

        expect(await screen.findByRole('link', { name: /Orden n° 1 · Toyota Yaris/ }))
            .toHaveAttribute('href', '/admin/ordenes/1');
        expect(screen.getByText('1–20 de 21')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));

        expect(await screen.findByRole('link', { name: /Orden n° 21 · Toyota Yaris/ }))
            .toHaveAttribute('href', '/admin/ordenes/21');
        expect(screen.getByText('21–21 de 21')).toBeInTheDocument();
        expect(orderService.getVehicleOrderHistory).toHaveBeenNthCalledWith(2, '12', {
            limit: 20,
            offset: 20,
        });
    });
});
