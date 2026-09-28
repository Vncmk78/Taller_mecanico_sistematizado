import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { ClientOrdersPage } from './ClientOrdersPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
    },
}));

function orden(id: string, vehicleId: string, estadoCodigo: number): Order {
    return {
        id,
        vehicleId,
        ingresoId: Number(id),
        estadoCodigo,
        mecanicoActualId: 'm1',
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: '2026-09-05T16:30:00',
        patente: `PT-${id}`,
        vehiculo: `Vehículo ${id}`,
    };
}

// El cliente demo (c1) es dueño de los vehículos 1 y 6 (mockVehicles).
const ordVeh1 = orden('101', '1', 5);
const ordVeh2 = orden('102', '2', 3);
const ordVeh6 = orden('106', '6', 6);

function renderPage() {
    return render(
        <MemoryRouter>
            <ClientOrdersPage />
        </MemoryRouter>
    );
}

describe('ClientOrdersPage: mis órdenes del cliente', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('online muestra todas las órdenes', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordVeh1, ordVeh2, ordVeh6]);

        renderPage();

        expect(await screen.findByText('Mis Órdenes')).toBeInTheDocument();
        expect(await screen.findByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 102')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 106')).toBeInTheDocument();
    });

    it('offline filtra por los vehículos del cliente y mantiene la caché', async () => {
        useOrderStore.setState({ orders: [ordVeh1, ordVeh2, ordVeh6], isOffline: true });
        vi.mocked(orderService.getOrders).mockRejectedValue(new Error('network'));

        renderPage();

        expect(
            await screen.findByText(/No se pudo conectar con el servidor/)
        ).toBeInTheDocument();
        expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 106')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 102')).not.toBeInTheDocument();
    });

    it('muestra el estado vacío cuando el cliente no tiene órdenes', async () => {
        useOrderStore.setState({ orders: [ordVeh2], isOffline: true });
        vi.mocked(orderService.getOrders).mockRejectedValue(new Error('network'));

        renderPage();

        expect(
            await screen.findByText('Aún no tiene órdenes de trabajo registradas.')
        ).toBeInTheDocument();
    });

    it('muestra el skeleton mientras carga', () => {
        vi.mocked(orderService.getOrders).mockImplementation(() => new Promise<Order[]>(() => {}));

        const { container } = renderPage();

        expect(container.querySelector('.animate-pulse')).not.toBeNull();
    });
});