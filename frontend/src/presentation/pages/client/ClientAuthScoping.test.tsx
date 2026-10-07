import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import type { User } from '@/domain/entities/User';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { orderService } from '@/infrastructure/api/OrderService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
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

// Vehículos demo: el cliente c1 posee los vehículos 1 y 6; el cliente c2 posee el 2.
const vehiculo1: Vehicle = { id: '1', patent: 'ABCD-12', brand: 'Ford', model: 'Fiesta', year: 2018, mileage: 85120, clientId: 'c1' };
const vehiculo2: Vehicle = { id: '2', patent: 'EFGH-34', brand: 'Nissan', model: 'Kicks', year: 2021, mileage: 32500, clientId: 'c2' };
const vehiculo6: Vehicle = { id: '6', patent: 'QWER-12', brand: 'Chevrolet', model: 'Spark', year: 2017, mileage: 110000, clientId: 'c1' };

// Cliente 2 autenticado: no es el cliente demo (c1).
const cliente2: User = {
    id: 'c2',
    email: 'cliente2@taller.cl',
    full_name: 'Cliente Dos',
    role: 'cliente',
    is_active: true,
};

const axiosNetworkError = { isAxiosError: true };

function renderPage() {
    return render(
        <MemoryRouter>
            <ClientOrdersPage />
        </MemoryRouter>
    );
}

describe('Visualización de información según el cliente autenticado', () => {
    beforeEach(() => {
        useAuthStore.setState({ user: null, token: null, isAuthenticated: false, isLoading: false, isInitializing: false });
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useVehicleStore.setState({ vehicles: [vehiculo1, vehiculo2, vehiculo6], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('ClientOrdersPage offline muestra solo las órdenes del cliente autenticado', async () => {
        useAuthStore.setState({
            user: cliente2,
            token: 'token-c2',
            isAuthenticated: true,
            isLoading: false,
            isInitializing: false,
        });
        useOrderStore.setState({
            orders: [orden('101', '1', 5), orden('102', '2', 5), orden('106', '6', 5)],
            status: 'idle',
            error: null,
            isOffline: true,
        });
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(
            await screen.findByText(/No se pudo conectar con el servidor/)
        ).toBeInTheDocument();
        expect(screen.getByText('Orden n° 102')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 101')).not.toBeInTheDocument();
        expect(screen.queryByText('Orden n° 106')).not.toBeInTheDocument();
    });
});