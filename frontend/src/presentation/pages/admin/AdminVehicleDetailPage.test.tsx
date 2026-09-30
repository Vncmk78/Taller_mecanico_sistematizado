import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { AdminVehicleDetailPage } from './AdminVehicleDetailPage';

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
// Error de transporte: no llegó respuesta HTTP, así que es "sin conexión".
const axiosNetworkError = { isAxiosError: true };

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/admin/vehiculos/1']}>
            <Routes>
                <Route path="/admin/vehiculos/:id" element={<AdminVehicleDetailPage />} />
            </Routes>
        </MemoryRouter>
    );
}

describe('AdminVehicleDetailPage: ficha del vehículo', () => {
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

    it('un 404 real muestra el estado vacío, no un error', async () => {
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(axios404);

        renderPage();

        expect(await screen.findByText('Vehículo no encontrado.')).toBeInTheDocument();
        expect(screen.queryByText('No se pudo cargar la ficha del vehículo')).not.toBeInTheDocument();
    });

    it('un error del servidor sin caché muestra un error reintentable', async () => {
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudo cargar la ficha del vehículo')).toBeInTheDocument();
        expect(screen.getByText('El servidor tuvo un problema. Intente más tarde.')).toBeInTheDocument();
        // Un fallo de fetch no es un "no encontrado".
        expect(screen.queryByText('Vehículo no encontrado.')).not.toBeInTheDocument();
        // Y tampoco es un problema de conexión: llegó respuesta del servidor.
        expect(screen.queryByText(/No se pudo conectar con el servidor/)).not.toBeInTheDocument();
    });

    it('reintenta la carga desde el estado de error', async () => {
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(axios500);

        renderPage();

        const reintentar = await screen.findByRole('button', { name: 'Reintentar' });
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(vehiculo);
        fireEvent.click(reintentar);

        expect(await screen.findByText('ABCD-12')).toBeInTheDocument();
    });

    it('sin conexión conserva la ficha en caché y avisa', async () => {
        useVehicleStore.setState({ vehicles: [vehiculo] });
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(await screen.findByText('ABCD-12')).toBeInTheDocument();
        expect(screen.getByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
    });
});
