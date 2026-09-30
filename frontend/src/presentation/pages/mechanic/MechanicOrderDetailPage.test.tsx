import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { MechanicOrderDetailPage } from './MechanicOrderDetailPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
    },
}));

const orden: Order = {
    id: '101',
    vehicleId: '1',
    ingresoId: 1,
    estadoCodigo: 5,
    mecanicoActualId: 'm1',
    creadoPorId: 'u1',
    creadoEn: '2026-09-01T10:15:00',
    actualizadoEn: '2026-09-05T16:30:00',
    patente: 'ABCD-12',
    vehiculo: 'Ford Fiesta',
};

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/mechanic/ordenes/101']}>
            <Routes>
                <Route path="/mechanic/ordenes/:id" element={<MechanicOrderDetailPage />} />
            </Routes>
        </MemoryRouter>
    );
}

describe('MechanicOrderDetailPage: detalle desde el portal del mecánico', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useOrderHistoryStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('muestra el panel y el historial de la orden', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue(orden);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue([]);

        renderPage();

        expect(await screen.findByText('Orden de trabajo n° 101')).toBeInTheDocument();
        expect(await screen.findByRole('list', { name: 'Ciclo de estados de la orden' })).toBeInTheDocument();
    });

    it('muestra la orden no encontrada con el link de regreso', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios404);

        renderPage();

        expect(await screen.findByText(/Orden no encontrada/)).toBeInTheDocument();
        expect(
            screen.getByRole('link', { name: 'Volver a mis órdenes' })
        ).toHaveAttribute('href', '/mechanic/ordenes');
    });

    it('muestra estado de error cuando falla el fetch sin caché', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudo cargar el detalle de la orden')).toBeInTheDocument();
        expect(screen.queryByText(/Orden no encontrada/)).not.toBeInTheDocument();
    });
});