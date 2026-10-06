import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
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

const axiosNetworkError = { isAxiosError: true };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

function renderPage() {
    return render(
        <MemoryRouter>
            <ClientServicesPage />
        </MemoryRouter>
    );
}

describe('ClientServicesPage: estado del servicio (consulta de servicios)', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false, requestId: null });
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

    it('queda offline, conserva la caché de servicios del cliente', async () => {
        useOrderStore.setState({
            orders: [servicio('101', 5, '1', 'ABCD-12')],
            status: 'idle',
            error: null,
            isOffline: false,
        });
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
        expect(screen.getByText('Servicio n° 101')).toBeInTheDocument();
    });

    it('un error del servidor sin caché lo muestra con ErrorState y reintento', async () => {
        vi.mocked(orderService.getOrders).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudieron cargar sus servicios')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
        expect(screen.queryByText('No se pudo conectar con el servidor.')).not.toBeInTheDocument();
    });
});