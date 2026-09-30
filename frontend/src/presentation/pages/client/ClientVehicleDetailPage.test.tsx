import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
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
});
