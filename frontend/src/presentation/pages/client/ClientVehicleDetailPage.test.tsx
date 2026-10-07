import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import type { User } from '@/domain/entities/User';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { orderService } from '@/infrastructure/api/OrderService';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { ClientVehicleDetailPage } from './ClientVehicleDetailPage';

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getAllVehicles: vi.fn(),
        getMyVehicles: vi.fn(),
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
        cambiarEstado: vi.fn(),
    },
}));

// Identidad real de la sesión (usuario_id de MS1).
const CLIENTE_ID = 'c1';

const mio: Vehicle = {
    id: '1',
    patent: 'ABCD-12',
    brand: 'Ford',
    model: 'Fiesta',
    year: 2020,
    mileage: 10000,
    clientId: CLIENTE_ID,
};

const deOtro: Vehicle = {
    id: '2',
    patent: 'EFGH-34',
    brand: 'Nissan',
    model: 'Kicks',
    year: 2021,
    mileage: 20000,
    clientId: 'c2',
};

// Sesión de un cliente distinto al dueño del vehículo 1 (que es el cliente demo).
const otroCliente: User = {
    id: 'cliente-otro',
    email: 'otro@taller.cl',
    full_name: 'Otro Cliente',
    role: 'cliente',
    is_active: true,
};

const ordenDelVehiculo: Order = {
    id: '101',
    vehicleId: '1',
    ingresoId: 1,
    estadoCodigo: 3,
    mecanicoActualId: null,
    creadoPorId: CLIENTE_ID,
    creadoEn: '2026-09-19T15:00:00.000Z',
    actualizadoEn: '2026-09-20T10:00:00.000Z',
};

const ordenDeOtroVehiculo: Order = {
    id: '102',
    vehicleId: '2',
    ingresoId: 2,
    estadoCodigo: 5,
    mecanicoActualId: null,
    creadoPorId: 'c2',
    creadoEn: '2026-09-18T15:00:00.000Z',
    actualizadoEn: '2026-09-19T10:00:00.000Z',
};

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

function renderPage(id = '1') {
    return render(
        <MemoryRouter initialEntries={[`/client/vehiculos/${id}`]}>
            <Routes>
                <Route path="/client/vehiculos/:id" element={<ClientVehicleDetailPage />} />
            </Routes>
        </MemoryRouter>
    );
}

describe('ClientVehicleDetailPage: ficha de un vehículo propio', () => {
    beforeEach(() => {
        useAuthStore.setState({
            user: {
                id: CLIENTE_ID,
                email: 'cliente@taller.cl',
                full_name: 'Cliente Prueba',
                role: 'cliente',
                is_active: true,
            },
        });
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        vi.mocked(orderService.getOrders).mockResolvedValue([]);
        vi.clearAllMocks();
    });

    it('muestra la ficha del vehículo del cliente', async () => {
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(mio);

        renderPage();

        expect(await screen.findByText('ABCD-12')).toBeInTheDocument();
        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
    });

    it('un 404 real muestra el estado vacío del cliente', async () => {
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(axios404);

        renderPage();

        expect(
            await screen.findByText('Vehículo no encontrado o no pertenece a su cuenta.')
        ).toBeInTheDocument();
        expect(screen.queryByText('No se pudo cargar la ficha del vehículo')).not.toBeInTheDocument();
    });

    it('un vehículo de otro cliente en la caché no se muestra como propio', async () => {
        // La caché es compartida entre portales: el chequeo de pertenencia en la
        // vista es lo que evita exponer la ficha de otro cliente.
        useVehicleStore.setState({ vehicles: [deOtro] });
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(axios404);

        renderPage('2');

        expect(
            await screen.findByText('Vehículo no encontrado o no pertenece a su cuenta.')
        ).toBeInTheDocument();
        expect(screen.queryByText('EFGH-34')).not.toBeInTheDocument();
        expect(screen.queryByText('Nissan Kicks')).not.toBeInTheDocument();
    });

    it('un error del servidor sin caché no lo disfraza de "no encontrado"', async () => {
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudo cargar la ficha del vehículo')).toBeInTheDocument();
        expect(
            screen.queryByText('Vehículo no encontrado o no pertenece a su cuenta.')
        ).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
        expect(
            screen.getByRole('link', { name: 'Volver a mis vehículos' })
        ).toHaveAttribute('href', '/client/vehiculos');
    });

    it('lista solo las órdenes del vehículo consultado en el historial', async () => {
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(mio);
        vi.mocked(orderService.getOrders).mockResolvedValue([
            ordenDelVehiculo,
            ordenDeOtroVehiculo,
        ]);

        renderPage('1');

        const linkOrdenPropia = await screen.findByRole('link', {
            name: /Orden n° 101 · Ford Fiesta/,
        });
        expect(linkOrdenPropia).toHaveAttribute('href', '/client/ordenes/101');
        expect(screen.getByText('Actualizada el', { exact: false })).toBeInTheDocument();
        expect(screen.getByText('1 orden')).toBeInTheDocument();
        expect(screen.queryByRole('link', { name: /Orden n° 102/ })).not.toBeInTheDocument();
    });

    it('muestra mensaje de historial vacío cuando no hay órdenes', async () => {
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(mio);
        vi.mocked(orderService.getOrders).mockResolvedValue([]);

        renderPage('1');

        expect(
            await screen.findByText('Este vehículo aún no tiene órdenes de trabajo registradas.')
        ).toBeInTheDocument();
    });

    it('muestra un error reintentable en el historial cuando no se pueden cargar las órdenes', async () => {
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(mio);
        vi.mocked(orderService.getOrders).mockRejectedValue(axios500);

        renderPage('1');

        expect(
            await screen.findByText('El servidor tuvo un problema. Intente más tarde.')
        ).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
        expect(
            screen.queryByText('Este vehículo aún no tiene órdenes de trabajo registradas.')
        ).not.toBeInTheDocument();
    });

    it('el control de pertenencia usa la identidad de la sesión, no un id fijo', async () => {
        useAuthStore.setState({
            user: otroCliente,
            token: 'token-otro',
            isAuthenticated: true,
            isLoading: false,
            isInitializing: false,
        });
        useVehicleStore.setState({ vehicles: [mio], status: 'idle', error: null, isOffline: false });
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(mio);

        renderPage('1');

        expect(
            await screen.findByText('Vehículo no encontrado o no pertenece a su cuenta.')
        ).toBeInTheDocument();
        // Aunque el demo (c1) sería "dueño", la sesión es de otro cliente: no se ve la placa.
        expect(screen.queryByText('ABCD-12')).not.toBeInTheDocument();
    });
});