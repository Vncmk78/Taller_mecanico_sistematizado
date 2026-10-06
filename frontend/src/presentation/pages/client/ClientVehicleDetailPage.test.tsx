import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { orderService } from '@/infrastructure/api/OrderService';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { ClientVehicleDetailPage } from './ClientVehicleDetailPage';

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getMyVehicles: vi.fn(),
        getAllVehicles: vi.fn(),
        getAssignedVehicles: vi.fn(),
        getVehicleById: vi.fn(),
        createVehicle: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
    },
}));

// El vehículo 1 pertenece al cliente demo c1; los vehículos 2 y 6, no.
const vehiculo: Vehicle = { id: '1', patent: 'ABCD-12', brand: 'Ford', model: 'Fiesta', year: 2018, mileage: 85120, clientId: 'c1' };

function orden(id: string, vehicleId: string, estadoCodigo: number): Order {
    return {
        id,
        vehicleId,
        ingresoId: Number(id),
        estadoCodigo,
        mecanicoActualId: 'm1',
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: `2026-09-${id}T10:00:00`,
        patente: 'ABCD-12',
        vehiculo: 'Ford Fiesta',
    };
}

const axiosNetworkError = { isAxiosError: true };

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/client/vehiculos/1']}>
            <Routes>
                <Route path="/client/vehiculos/:id" element={<ClientVehicleDetailPage />} />
            </Routes>
        </MemoryRouter>
    );
}

describe('ClientVehicleDetailPage: ficha del vehículo con historial de órdenes', () => {
    beforeEach(() => {
        useVehicleStore.setState({ vehicles: [vehiculo], status: 'idle', error: null, isOffline: false });
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('muestra la ficha y el historial de órdenes del vehículo consultado', async () => {
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(vehiculo);
        vi.mocked(orderService.getOrders).mockResolvedValue([
            orden('101', '1', 5),
            orden('102', '1', 3),
            orden('103', '6', 2),
        ]);

        renderPage();

        expect(await screen.findByText(/Orden n° 101/)).toBeInTheDocument();
        expect(screen.getByText(/Orden n° 102/)).toBeInTheDocument();
        // La orden del vehículo 6 no pertenece a este vehículo.
        expect(screen.queryByText(/Orden n° 103/)).not.toBeInTheDocument();
        expect(screen.getByText('2 órdenes')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /Orden n° 101/ })).toHaveAttribute(
            'href',
            '/client/ordenes/101'
        );
        expect(screen.getByTitle('En reparación')).toBeInTheDocument();
        expect(screen.getByTitle('Esperando aprobación de presupuesto')).toBeInTheDocument();
    });

    it('muestra mensaje cuando el vehículo aún no tiene órdenes', async () => {
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(vehiculo);
        vi.mocked(orderService.getOrders).mockResolvedValue([]);

        renderPage();

        expect(
            await screen.findByText('Este vehículo aún no tiene órdenes de trabajo registradas.')
        ).toBeInTheDocument();
    });

    it('muestra estado de error cuando falla la carga del vehículo sin caché', async () => {
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(
            await screen.findByText('No se pudieron cargar los datos del vehículo')
        ).toBeInTheDocument();
        expect(screen.getByText('Reintentar')).toBeInTheDocument();
        expect(
            screen.queryByText(/Vehículo no encontrado o no pertenece a su cuenta/)
        ).not.toBeInTheDocument();
    });

    it('muestra estado de error en el historial cuando no se pueden cargar las órdenes', async () => {
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(vehiculo);
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(
            await screen.findByText('No se pudieron cargar las órdenes del vehículo.')
        ).toBeInTheDocument();
        expect(
            screen.queryByText('Este vehículo aún no tiene órdenes de trabajo registradas.')
        ).not.toBeInTheDocument();
    });
});