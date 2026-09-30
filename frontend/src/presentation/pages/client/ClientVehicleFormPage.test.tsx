import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { errorAxios, errorInternoGateway, gatewaySaturada, patenteDuplicada } from '@/infrastructure/mocks/payloads.reales';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { ClientVehicleFormPage } from './ClientVehicleFormPage';

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getMyVehicles: vi.fn(),
        getAllVehicles: vi.fn(),
        getAssignedVehicles: vi.fn(),
        getVehicleById: vi.fn(),
        createVehicle: vi.fn(),
    },
}));

const CLIENTE_ID = '7';

// Datos válidos según el formulario. La patente sigue el formato que exige la
// validación del cliente (4 letras, guion, 2 dígitos).
const DATOS = {
    patent: 'ZZZZ-11',
    brand: 'Toyota',
    model: 'Corolla',
    year: '2018',
    mileage: '45000',
};

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/client/vehiculos/nuevo']}>
            <Routes>
                <Route path="/client/vehiculos/nuevo" element={<ClientVehicleFormPage />} />
                <Route path="/client/vehiculos" element={<p>Listado de vehículos</p>} />
            </Routes>
        </MemoryRouter>
    );
}

function completarFormulario() {
    fireEvent.change(screen.getByLabelText(/Patente/), { target: { value: DATOS.patent } });
    fireEvent.change(screen.getByLabelText(/Marca/), { target: { value: DATOS.brand } });
    fireEvent.change(screen.getByLabelText(/Modelo/), { target: { value: DATOS.model } });
    fireEvent.change(screen.getByLabelText(/Año/), { target: { value: DATOS.year } });
    fireEvent.change(screen.getByLabelText(/Kilometraje actual/), { target: { value: DATOS.mileage } });
}

describe('ClientVehicleFormPage: errores reales del backend al registrar', () => {
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
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('muestra el mensaje real de MS2 cuando la patente ya está registrada (409)', async () => {
        vi.mocked(vehicleService.createVehicle).mockRejectedValue(errorAxios(409, patenteDuplicada));

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        // El 409 real trae este literal; la UI lo muestra en el campo patente
        // en vez de un texto propio, para que el motivo sea el del servidor.
        expect(await screen.findByText('La patente ya está registrada')).toBeInTheDocument();
        // Y no cae en el error genérico del formulario.
        expect(screen.queryByText(/No pudimos registrar el vehículo/)).not.toBeInTheDocument();
    });

    it('muestra el mensaje real de la Gateway ante un 500 con su reference', async () => {
        vi.mocked(vehicleService.createVehicle).mockRejectedValue(errorAxios(500, errorInternoGateway));

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        expect(await screen.findByText('Ocurrió un error inesperado en la Gateway.')).toBeInTheDocument();
        // El request_id permite rastrear el fallo en los logs del backend.
        expect(screen.getByText(/Referencia: 9f1c2b3a-4d5e-6f70-8192-a3b4c5d6e7f8/)).toBeInTheDocument();
    });

    it('propaga el mensaje de saturación de la Gateway (503) sin inventar otro texto', async () => {
        vi.mocked(vehicleService.createVehicle).mockRejectedValue(errorAxios(503, gatewaySaturada));

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        expect(await screen.findByText('La Gateway está ocupada. Intente más tarde.')).toBeInTheDocument();
    });

    it('omite la referencia cuando el error no trae request_id', async () => {
        // Un 422 de validación de FastAPI no lleva request_id: no hay nada que
        // rastrear, así que no se muestra una referencia inventada.
        vi.mocked(vehicleService.createVehicle).mockRejectedValue(
            errorAxios(422, { detail: [{ loc: ['body', 'patente'], msg: 'String should have at least 1 character' }] })
        );

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        expect(await screen.findByText('String should have at least 1 character')).toBeInTheDocument();
        expect(screen.queryByText(/Referencia:/)).not.toBeInTheDocument();
    });

    it('registra el vehículo y vuelve al listado cuando la Gateway responde bien', async () => {
        vi.mocked(vehicleService.createVehicle).mockResolvedValue({
            id: '12',
            patent: 'ZZZZ-11',
            brand: 'Toyota',
            model: 'Corolla',
            year: 2018,
            mileage: 45000,
            clientId: CLIENTE_ID,
        });

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        await waitFor(() => expect(screen.getByText('Listado de vehículos')).toBeInTheDocument());
        expect(vehicleService.createVehicle).toHaveBeenCalledWith({
            patent: 'ZZZZ-11',
            brand: 'Toyota',
            model: 'Corolla',
            year: 2018,
            mileage: 45000,
        });
    });

    it('no llama a la Gateway si el propio formulario ya detecta la patente repetida', async () => {
        // Verificación optimista: evita un viaje de ida y vuelta cuando el
        // duplicado ya está en la caché local.
        useVehicleStore.setState({
            vehicles: [
                { id: '12', patent: 'ZZZZ-11', brand: 'Toyota', model: 'Corolla', year: 2018, mileage: 45000, clientId: CLIENTE_ID },
            ],
        });

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        expect(await screen.findByText('Ya existe un vehículo registrado con esa patente.')).toBeInTheDocument();
        expect(vehicleService.createVehicle).not.toHaveBeenCalled();
    });
});
