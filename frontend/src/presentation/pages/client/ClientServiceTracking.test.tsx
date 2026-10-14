import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { ClientOrderDetailPage } from './ClientOrderDetailPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
    },
}));

const servicio: Order = {
    id: '101',
    vehicleId: '1',
    ingresoId: 1,
    estadoCodigo: 3,
    mecanicoActualId: '1',
    creadoPorId: 'u1',
    creadoEn: '2026-09-01T10:15:00',
    actualizadoEn: '2026-09-04T12:20:00',
    patente: 'ABCD-12',
    vehiculo: 'Ford Fiesta',
    mecanicoNombre: 'Martín Herrera',
};

const historialOrden101: OrderHistoryEntry[] = [
    {
        id: 'h-101-1',
        ordenId: '101',
        estadoAnteriorCodigo: null,
        estadoNuevoCodigo: 1,
        actorUsuarioId: null,
        origen: 'sistema',
        fecha: '2026-09-01T10:15:00',
        observacion: 'Ingreso registrado por el administrador',
    },
    {
        id: 'h-101-2',
        ordenId: '101',
        estadoAnteriorCodigo: 1,
        estadoNuevoCodigo: 2,
        actorUsuarioId: 7,
        origen: 'usuario',
        fecha: '2026-09-01T11:00:00',
        observacion: 'Asignada a Martín Herrera',
        usuarioNombre: 'Administrador del taller',
    },
    {
        id: 'h-101-3',
        ordenId: '101',
        estadoAnteriorCodigo: 2,
        estadoNuevoCodigo: 3,
        actorUsuarioId: 1,
        origen: 'usuario',
        fecha: '2026-09-02T09:20:00',
        observacion: 'Presupuesto v1 enviado al cliente',
        usuarioNombre: 'Martín Herrera',
    },
];

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };
const axiosNetworkError = { isAxiosError: true };

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/client/ordenes/101']}>
            <Routes>
                <Route path="/client/ordenes/:id" element={<ClientOrderDetailPage />} />
            </Routes>
        </MemoryRouter>
    );
}

describe('ClientOrderDetailPage: detalle de estado y seguimiento del servicio', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useOrderHistoryStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('muestra el estado actual destacado y el seguimiento con fechas y observaciones', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue(servicio);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(historialOrden101);

        renderPage();

        expect(await screen.findByText('Orden de trabajo n° 101')).toBeInTheDocument();
        expect(
            screen.getByRole('list', { name: 'Ciclo de estados de la orden' })
        ).toBeInTheDocument();

        // El estado actual (3: Esperando aprobación de presupuesto) queda marcado.
        expect(
            screen.getByRole('listitem', { name: 'Estado 3: Esperando aprobación de presupuesto' })
        ).toHaveAttribute('aria-current', 'step');

        // Seguimiento: historial con fechas y observaciones.
        expect(screen.getByRole('heading', { name: 'Historial de estados' })).toBeInTheDocument();
        expect(await screen.findByText('Presupuesto v1 enviado al cliente')).toBeInTheDocument();
        expect(screen.getByText('Ingreso registrado por el administrador')).toBeInTheDocument();
    });

    it('un error del servidor sin caché no lo disfraza de orden no encontrada', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios500);

        renderPage();

        expect(
            await screen.findByText('No se pudo cargar el detalle de la orden')
        ).toBeInTheDocument();
        expect(screen.getByText('Reintentar')).toBeInTheDocument();
        expect(screen.queryByText(/Orden no encontrada/)).not.toBeInTheDocument();
    });

    it('una orden inexistente (404) muestra el estado vacío con el enlace de regreso', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios404);

        renderPage();

        expect(await screen.findByText(/Orden no encontrada/)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Volver a mis órdenes' })).toHaveAttribute(
            'href',
            '/client/ordenes'
        );
    });

    it('sin conexión conserva el detalle y el seguimiento desde la caché', async () => {
        useOrderStore.setState({ orders: [servicio], error: null, isOffline: false });
        useOrderHistoryStore.setState({
            entries: [historialOrden101[2]],
            status: 'error',
            error: 'No se pudo conectar con el servidor.',
            isOffline: true,
        });
        vi.mocked(orderService.getOrderById).mockRejectedValue(axiosNetworkError);
        vi.mocked(orderService.getOrderHistory).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(await screen.findByText('Orden de trabajo n° 101')).toBeInTheDocument();
        expect(
            await screen.findAllByText(/No se pudo conectar con el servidor/)
        ).toHaveLength(2);
        expect(await screen.findByText('Presupuesto v1 enviado al cliente')).toBeInTheDocument();
        expect(
            screen.queryByText('No se pudieron cargar los datos del servicio')
        ).not.toBeInTheDocument();
    });

    it('un error del servidor con copia en caché conserva la orden y el seguimiento', async () => {
        useOrderStore.setState({ orders: [servicio], error: null, isOffline: false });
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios500);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(historialOrden101);

        renderPage();

        expect(await screen.findByText('Orden de trabajo n° 101')).toBeInTheDocument();
        expect(
            screen.getByRole('list', { name: 'Ciclo de estados de la orden' })
        ).toBeInTheDocument();
        expect(
            await screen.findByText('Presupuesto v1 enviado al cliente')
        ).toBeInTheDocument();
        expect(
            screen.queryByText('No se pudieron cargar los datos del servicio')
        ).not.toBeInTheDocument();
    });
});