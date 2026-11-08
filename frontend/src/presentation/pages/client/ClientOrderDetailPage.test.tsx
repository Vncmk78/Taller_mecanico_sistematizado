import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { orderService } from '@/infrastructure/api/OrderService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { ClientOrderDetailPage } from './ClientOrderDetailPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
        cambiarEstado: vi.fn(),
        asignarMecanico: vi.fn(),
        registrarEntrega: vi.fn(),
        cancelarComoCliente: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/NuevaAtencionService', () => ({
    nuevaAtencionService: { solicitar: vi.fn(), listar: vi.fn(), obtener: vi.fn() },
}));

const orden: Order = {
    id: '101',
    vehicleId: '1',
    ingresoId: 1,
    estadoCodigo: 5,
    mecanicoActualId: 'm1',
    creadoPorId: 'u1',
    creadoEn: '2026-09-01T10:15:00',
    actualizadoEn: '2026-09-05T16:30:00',
    patente: 'ABCD-12',
    vehiculo: 'Ford Fiesta',
    mecanicoNombre: 'Martín Herrera',
};

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/client/ordenes/101']}>
            <ToastProvider>
                <Routes>
                    <Route path="/client/ordenes/:id" element={<ClientOrderDetailPage />} />
                </Routes>
            </ToastProvider>
        </MemoryRouter>
    );
}

describe('ClientOrderDetailPage: detalle desde el portal del cliente', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useOrderHistoryStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
        useAuthStore.setState({ user: null, token: null, isAuthenticated: false });
        vi.clearAllMocks();
    });

    it('muestra el panel y el historial de la orden', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue(orden);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue([]);

        renderPage();

        expect(await screen.findByText('Orden de trabajo n° 101')).toBeInTheDocument();
        expect(await screen.findByRole('list', { name: 'Ciclo de estados de la orden' })).toBeInTheDocument();
    });

    it('muestra la orden no encontrada con el link de regreso', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios404);

        renderPage();

        expect(await screen.findByText(/Orden no encontrada/)).toBeInTheDocument();
        expect(
            screen.getByRole('link', { name: 'Volver a mis órdenes' })
        ).toHaveAttribute('href', '/client/ordenes');
    });

    it('muestra estado de error cuando falla el fetch sin caché', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudo cargar el detalle de la orden')).toBeInTheDocument();
        expect(screen.queryByText(/Orden no encontrada/)).not.toBeInTheDocument();
    });

    it('ofrece al cliente gestionar el presupuesto y cancelar su solicitud', async () => {
        useAuthStore.setState({
            user: { id: '99', email: 'cliente@taller.cl', full_name: 'Cliente', role: 'cliente', is_active: true },
            token: 't',
            isAuthenticated: true,
        });
        vi.mocked(orderService.getOrderById).mockResolvedValue({ ...orden, estadoCodigo: 3 });
        vi.mocked(orderService.getOrderHistory).mockResolvedValue([]);

        renderPage();

        expect(await screen.findByRole('link', { name: 'Gestionar presupuesto' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Solicitar cancelación' })).toBeInTheDocument();
    });
});

describe('ClientOrderDetailPage: nueva atención de una orden cancelada', () => {
    const cliente = {
        id: '10', email: 'c@taller.cl', full_name: 'Cliente', role: 'cliente' as const,
        roles: ['cliente' as const], is_active: true,
    };

    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useOrderHistoryStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
        useAuthStore.setState({ user: cliente, token: 't', isAuthenticated: true });
        vi.clearAllMocks();
        vi.mocked(orderService.getOrderHistory).mockResolvedValue([]);
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    });

    it('la orden Cancelada propia (ya autorizada por el GET) ofrece solicitar nueva atención', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue({
            ...orden, estadoCodigo: 8, mecanicoActualId: null, mecanicoNombre: undefined,
            devueltoEn: null, devueltoPorId: null,
        });

        renderPage();

        expect(await screen.findByRole('heading', { name: 'Nueva atención' })).toBeInTheDocument();
        expect(await screen.findByRole('button', { name: 'Enviar solicitud' })).toBeInTheDocument();
        expect(nuevaAtencionService.listar).toHaveBeenCalledWith({ ordenCanceladaId: '101' }, { limit: 20, offset: 0 });
    });

    it('una orden activa no la ofrece', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue(orden);

        renderPage();

        expect(await screen.findByText('Orden de trabajo n° 101')).toBeInTheDocument();
        expect(screen.queryByRole('heading', { name: 'Nueva atención' })).not.toBeInTheDocument();
        expect(nuevaAtencionService.listar).not.toHaveBeenCalled();
    });

    it('una orden ajena o inexistente (404) no muestra el formulario', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios404);

        renderPage();

        expect(await screen.findByText(/Orden no encontrada/)).toBeInTheDocument();
        expect(screen.queryByRole('heading', { name: 'Nueva atención' })).not.toBeInTheDocument();
    });
});

