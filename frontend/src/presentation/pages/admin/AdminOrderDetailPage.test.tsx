import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { mockOrderHistory } from '@/infrastructure/mocks/orders.history.mock';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { AdminOrderDetailPage } from './AdminOrderDetailPage';

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
    mecanicoNombre: 'Martín Herrera',
};

const hist101 = mockOrderHistory.filter((e) => e.ordenId === '101');

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

// Error de red simulado: es un error Axios pero sin respuesta HTTP del servidor.
const axiosNetworkError = { isAxiosError: true };

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/admin/ordenes/101']}>
            <Routes>
                <Route path="/admin/ordenes/:id" element={<AdminOrderDetailPage />} />
            </Routes>
        </MemoryRouter>
    );
}

describe('AdminOrderDetailPage: detalle con panel e historial', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useOrderHistoryStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('muestra el panel con los datos y el historial integrado', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue(orden);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);

        renderPage();

        expect(await screen.findByText('Orden de trabajo n° 101')).toBeInTheDocument();
        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getAllByText('Martín Herrera').length).toBeGreaterThan(0);

        expect(await screen.findByRole('list', { name: 'Ciclo de estados de la orden' })).toBeInTheDocument();
        expect(screen.getAllByRole('listitem')).toHaveLength(8);

        expect(
            await screen.findByText('Ingreso registrado por el administrador')
        ).toBeInTheDocument();
        expect(screen.getByText('desde Esperando aprobación de presupuesto')).toBeInTheDocument();
    });

    it('muestra la orden no encontrada con el link de regreso', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios404);

        renderPage();

        expect(await screen.findByText(/Orden no encontrada/)).toBeInTheDocument();
        expect(
            screen.getByRole('link', { name: 'Volver a la gestión de órdenes' })
        ).toHaveAttribute('href', '/admin/ordenes');
    });

    it('muestra estado de error cuando falla el fetch sin caché', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudo cargar el detalle de la orden')).toBeInTheDocument();
        // Un fallo de fetch no debe confundirse con un 404.
        expect(screen.queryByText(/Orden no encontrada/)).not.toBeInTheDocument();
    });

    it('reintenta la carga desde el estado de error', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios500);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);

        renderPage();

        const reintentar = await screen.findByRole('button', { name: 'Reintentar' });
        vi.mocked(orderService.getOrderById).mockResolvedValue(orden);
        fireEvent.click(reintentar);

        expect(await screen.findByText('Orden de trabajo n° 101')).toBeInTheDocument();
    });

    it('queda offline con banner y muestra la caché local', async () => {
        useOrderStore.setState({ orders: [orden] });
        vi.mocked(orderService.getOrderById).mockRejectedValue(axiosNetworkError);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);

        renderPage();

        expect(
            await screen.findByText(/No se pudo conectar con el servidor/)
        ).toBeInTheDocument();
        expect(screen.getByText('Orden de trabajo n° 101')).toBeInTheDocument();
    });

    it('muestra el estado de carga inicial', () => {
        vi.mocked(orderService.getOrderById).mockImplementation(() => new Promise<Order>(() => {}));

        renderPage();

        expect(screen.getByText('Cargando detalle de la orden...')).toBeInTheDocument();
    });
});