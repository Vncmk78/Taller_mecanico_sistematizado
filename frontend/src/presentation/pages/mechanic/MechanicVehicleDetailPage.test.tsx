import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { MechanicVehicleDetailPage } from './MechanicVehicleDetailPage';

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getAllVehicles: vi.fn(),
        getMyVehicles: vi.fn(),
        getAssignedVehicles: vi.fn(),
        getVehicleById: vi.fn(),
        createVehicle: vi.fn(),
    },
}));

const vehiculo: Vehicle = {
    id: '1',
    patent: 'ABCD-12',
    brand: 'Ford',
    model: 'Fiesta',
    year: 2020,
    mileage: 10000,
    clientId: 'c1',
};

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/mechanic/vehiculos/1']}>
            <Routes>
                <Route path="/mechanic/vehiculos/:id" element={<MechanicVehicleDetailPage />} />
            </Routes>
        </MemoryRouter>
    );
}

describe('MechanicVehicleDetailPage: ficha de un vehículo asignado', () => {
    beforeEach(() => {
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('muestra la ficha del vehículo', async () => {
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(vehiculo);

        renderPage();

        expect(await screen.findByText('ABCD-12')).toBeInTheDocument();
        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
    });

    it('un 404 de la Gateway muestra el estado vacío con el texto del mecánico', async () => {
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(axios404);

        renderPage();

        expect(
            await screen.findByText('Vehículo no encontrado o no está entre sus órdenes asignadas.')
        ).toBeInTheDocument();
        expect(screen.queryByText('No se pudo cargar la ficha del vehículo')).not.toBeInTheDocument();
    });

    it('un error del servidor sin caché no lo disfraza de "no encontrado"', async () => {
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudo cargar la ficha del vehículo')).toBeInTheDocument();
        expect(
            screen.queryByText('Vehículo no encontrado o no está entre sus órdenes asignadas.')
        ).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
    });
});
