import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { ClientServicesPage } from './ClientServicesPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
    },
}));

function servicio(id: string, estadoCodigo: number, vehicleId: string, patente: string): Order {
    return {
        id,
        vehicleId,
        ingresoId: Number(id),
        estadoCodigo,
        mecanicoActualId: 'm1',
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: `2026-09-${id}T10:00:00`,
        patente,
    };
}

// El cliente demo c1 es dueño de los vehículos 1 (estado 3: presupuesto por
// aprobar) y 6; el vehículo 2 pertenece a otro cliente.
const vehiculoC1: Vehicle = { id: '1', patent: 'ABCD-12', brand: 'Ford', model: 'Fiesta', year: 2018, mileage: 0, clientId: 'c1' };
const vehiculoAjeno: Vehicle = { id: '2', patent: 'EFGH-34', brand: 'Nissan', model: 'Kicks', year: 2021, mileage: 0, clientId: 'c2' };

const axiosNetworkError = { isAxiosError: true };

function renderPage() {
    return render(
        <MemoryRouter>
            <ClientServicesPage />
        </MemoryRouter>
    );
}

describe('ClientServicesPage: estado del servicio (consulta de servicios)', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useVehicleStore.setState({ vehicles: [vehiculoC1, vehiculoAjeno], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('agrupa los servicios por estado y resalta los que requieren atención', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([
            servicio('101', 3, '1', 'ABCD-12'),
            servicio('102', 1, '1', 'ABCD-12'),
            servicio('103', 7, '1', 'ABCD-12'),
        ]);

        renderPage();

        expect(await screen.findByText('Servicio n° 101')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: /Requieren su atención/ })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: /En proceso/ })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: /Finalizados/ })).toBeInTheDocument();

        expect(
            screen.getByText('Requiere su atención: presupuesto por aprobar')
        ).toBeInTheDocument();
        expect(screen.getByTitle('Esperando aprobación de presupuesto')).toBeInTheDocument();
        expect(screen.getByTitle('Recibido')).toBeInTheDocument();
        expect(screen.getByTitle('Entregado')).toBeInTheDocument();
        expect(screen.getAllByRole('link', { name: 'Ver detalle' })).toHaveLength(3);
    });

    it('muestra el mensaje vacío cuando el cliente no tiene servicios', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([]);

        renderPage();

        expect(
            await screen.findByText('Aún no tiene servicios en el taller')
        ).toBeInTheDocument();
    });

    it('queda offline, conserva la caché y filtra por los vehículos del cliente', async () => {
        useOrderStore.setState({
            orders: [servicio('101', 5, '1', 'ABCD-12'), servicio('102', 5, '2', 'EFGH-34')],
            status: 'idle',
            error: null,
            isOffline: false,
        });
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();

        expect(screen.getByText('Servicio n° 101')).toBeInTheDocument();
        expect(screen.queryByText('Servicio n° 102')).not.toBeInTheDocument();
    });
});