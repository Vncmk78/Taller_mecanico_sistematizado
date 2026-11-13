import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { errorAxios, errorInternoGateway, sinRespuesta } from '@/infrastructure/mocks/payloads.reales';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { ClientVehicleEditPage } from './ClientVehicleEditPage';

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getMyVehicles: vi.fn(),
        getAllVehicles: vi.fn(),
        getAssignedVehicles: vi.fn(),
        getVehicleById: vi.fn(),
        createVehicle: vi.fn(),
        updateVehicle: vi.fn(),
    },
}));

const CLIENTE_ID = '7';

const vehiculo: Vehicle = {
    id: '12',
    patent: 'AB1234',
    brand: 'Toyota',
    model: 'Corolla',
    year: 2018,
    mileage: 45000,
    clientId: CLIENTE_ID,
};

function renderPage(id = '12') {
    return render(
        <MemoryRouter initialEntries={[`/client/vehiculos/${id}/editar`]}>
            <Routes>
                <Route path="/client/vehiculos/:id/editar" element={<ClientVehicleEditPage />} />
                <Route path="/client/vehiculos/:id" element={<p>Ficha del vehículo</p>} />
                <Route path="/client/vehiculos" element={<p>Listado de vehículos</p>} />
            </Routes>
        </MemoryRouter>
    );
}

describe('ClientVehicleEditPage: edición de un vehículo propio', () => {
    beforeEach(() => {
        useAuthStore.setState({
            user: {
                id: CLIENTE_ID,
                email: 'ana@correo.cl',
                full_name: 'Ana Pérez',
                role: 'cliente',
                is_active: true,
            },
        });
        useVehicleStore.setState({ vehicles: [vehiculo], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
        vi.mocked(vehicleService.getVehicleById).mockResolvedValue(vehiculo);
    });

    it('precarga los datos y no permite modificar la patente', async () => {
        renderPage();

        expect(await screen.findByDisplayValue('AB1234')).toBeInTheDocument();
        expect(screen.getByDisplayValue('Toyota')).toBeInTheDocument();
        expect(screen.getByDisplayValue('Corolla')).toBeInTheDocument();
        expect(screen.getByDisplayValue('2018')).toBeInTheDocument();
        expect(screen.getByDisplayValue('45000')).toBeInTheDocument();
        expect(screen.getByLabelText(/Patente/)).toHaveAttribute('readonly');
        expect(screen.getByText('La patente no se puede modificar.')).toBeInTheDocument();
    });

    it('envía solo los campos editables y vuelve a la ficha al guardar', async () => {
        vi.mocked(vehicleService.updateVehicle).mockResolvedValue({
            ...vehiculo,
            brand: 'Mazda',
            model: 'CX-5',
            year: 2021,
            mileage: 30000,
        });

        renderPage();

        fireEvent.change(await screen.findByDisplayValue('Toyota'), { target: { value: 'Mazda' } });
        fireEvent.change(screen.getByDisplayValue('Corolla'), { target: { value: 'CX-5' } });
        fireEvent.change(screen.getByDisplayValue('2018'), { target: { value: '2021' } });
        fireEvent.change(screen.getByDisplayValue('45000'), { target: { value: '30000' } });
        fireEvent.click(screen.getByRole('button', { name: 'Guardar Cambios' }));

        await waitFor(() => expect(screen.getByText('Ficha del vehículo')).toBeInTheDocument());
        expect(vehicleService.updateVehicle).toHaveBeenCalledWith(
            '12',
            { brand: 'Mazda', model: 'CX-5', year: 2021, mileage: 30000 },
            CLIENTE_ID
        );
        // La caché compartida queda con la respuesta del backend.
        expect(useVehicleStore.getState().vehicles.find((v) => v.id === '12')).toMatchObject({
            brand: 'Mazda',
            model: 'CX-5',
            clientId: CLIENTE_ID,
        });
    });

    it('permite dejar año y kilometraje sin dato enviando null', async () => {
        vi.mocked(vehicleService.updateVehicle).mockResolvedValue(vehiculo);

        renderPage();

        fireEvent.change(await screen.findByDisplayValue('2018'), { target: { value: '' } });
        fireEvent.change(screen.getByDisplayValue('45000'), { target: { value: '' } });
        fireEvent.click(screen.getByRole('button', { name: 'Guardar Cambios' }));

        await waitFor(() => expect(vehicleService.updateVehicle).toHaveBeenCalled());
        expect(vehicleService.updateVehicle).toHaveBeenCalledWith(
            '12',
            expect.objectContaining({ year: null, mileage: null }),
            CLIENTE_ID
        );
    });

    it('muestra el mensaje real de la Gateway si falla la actualización', async () => {
        vi.mocked(vehicleService.updateVehicle).mockRejectedValue(
            errorAxios(500, errorInternoGateway)
        );

        renderPage();

        fireEvent.click(await screen.findByRole('button', { name: 'Guardar Cambios' }));

        expect(await screen.findByText('Ocurrió un error inesperado en la Gateway.')).toBeInTheDocument();
        expect(screen.getByText(/Referencia: 9f1c2b3a-4d5e-6f70-8192-a3b4c5d6e7f8/)).toBeInTheDocument();
    });

    it('no permite editar el vehículo de otro cliente aunque esté en caché', async () => {
        useVehicleStore.setState({ vehicles: [{ ...vehiculo, clientId: 'otro' }] });
        // Sin respuesta del servidor se conserva la caché compartida, que puede
        // venir de otro portal y pertenecer a otra cuenta.
        vi.mocked(vehicleService.getVehicleById).mockRejectedValue(sinRespuesta);

        renderPage();

        expect(
            await screen.findByText('Vehículo no encontrado o no pertenece a su cuenta.')
        ).toBeInTheDocument();
        expect(vehicleService.updateVehicle).not.toHaveBeenCalled();
    });
});
