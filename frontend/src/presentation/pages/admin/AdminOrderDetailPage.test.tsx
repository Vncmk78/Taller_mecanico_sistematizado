import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { authService } from '@/infrastructure/api/AuthService';
import { orderService } from '@/infrastructure/api/OrderService';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import { mockOrderHistory } from '@/infrastructure/mocks/orders.history.mock';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useEvidenceStore } from '@/infrastructure/stores/useEvidenceStore';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { AdminOrderDetailPage } from './AdminOrderDetailPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
        cambiarEstado: vi.fn(),
        asignarMecanico: vi.fn(),
        registrarEntrega: vi.fn(),
        cancelarComoCliente: vi.fn(),
        registrarDevolucion: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/InventarioService', () => ({
    inventarioService: {
        getDisponibilidadOrden: vi.fn(),
        reservar: vi.fn(),
        confirmarDisponibilidad: vi.fn(),
        liberar: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/AuthService', () => ({
    authService: { listarUsuarios: vi.fn() },
}));

vi.mock('@/infrastructure/api/EvidenciaService', () => ({
    evidenciaService: {
        getByOrder: vi.fn(),
        getById: vi.fn(),
        getDownloadUrl: vi.fn(),
        crear: vi.fn(),
    },
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

const hist101 = mockOrderHistory.filter((e) => e.ordenId === '101');

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

// Error de red simulado: es un error Axios pero sin respuesta HTTP del servidor.
const axiosNetworkError = { isAxiosError: true };

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/admin/ordenes/101']}>
            <ToastProvider>
                <Routes>
                    <Route path="/admin/ordenes/:id" element={<AdminOrderDetailPage />} />
                </Routes>
            </ToastProvider>
        </MemoryRouter>
    );
}

describe('AdminOrderDetailPage: detalle con panel e historial', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useOrderHistoryStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
        useAuthStore.setState({ user: null, token: null, isAuthenticated: false });
        useEvidenceStore.getState().reset();
        vi.clearAllMocks();
        vi.mocked(evidenciaService.getByOrder).mockResolvedValue([]);
        vi.mocked(inventarioService.getDisponibilidadOrden).mockResolvedValue({
            ordenId: 101,
            disponible: true,
            repuestos: [],
            presupuestoId: 501,
            version: 2,
        });
    });

    it('muestra el panel con los datos y el historial integrado', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue(orden);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);

        renderPage();

        expect(await screen.findByText('Orden de trabajo n° 101')).toBeInTheDocument();
        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getAllByText('Martín Herrera').length).toBeGreaterThan(0);

        expect(await screen.findByRole('list', { name: 'Ciclo de estados de la orden' })).toBeInTheDocument();
        expect(screen.getAllByRole('listitem')).toHaveLength(8);

        expect(
            await screen.findByText('Ingreso registrado por el administrador')
        ).toBeInTheDocument();
        expect(screen.getByText('desde Esperando aprobación de presupuesto')).toBeInTheDocument();
    });

    it('muestra la orden no encontrada con el link de regreso', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios404);

        renderPage();

        expect(await screen.findByText(/Orden no encontrada/)).toBeInTheDocument();
        expect(
            screen.getByRole('link', { name: 'Volver a la gestión de órdenes' })
        ).toHaveAttribute('href', '/admin/ordenes');
    });

    it('muestra estado de error cuando falla el fetch sin caché', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudo cargar el detalle de la orden')).toBeInTheDocument();
        // Un fallo de fetch no debe confundirse con un 404.
        expect(screen.queryByText(/Orden no encontrada/)).not.toBeInTheDocument();
    });

    it('reintenta la carga desde el estado de error', async () => {
        vi.mocked(orderService.getOrderById).mockRejectedValue(axios500);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);

        renderPage();

        const reintentar = await screen.findByRole('button', { name: 'Reintentar' });
        vi.mocked(orderService.getOrderById).mockResolvedValue(orden);
        fireEvent.click(reintentar);

        expect(await screen.findByText('Orden de trabajo n° 101')).toBeInTheDocument();
    });

    it('queda offline con banner y muestra la caché local', async () => {
        useOrderStore.setState({ orders: [orden] });
        vi.mocked(orderService.getOrderById).mockRejectedValue(axiosNetworkError);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);

        renderPage();

        expect(
            await screen.findByText(/No se pudo conectar con el servidor/)
        ).toBeInTheDocument();
        expect(screen.getByText('Orden de trabajo n° 101')).toBeInTheDocument();
    });

    it('muestra el estado de carga inicial', () => {
        vi.mocked(orderService.getOrderById).mockImplementation(() => new Promise<Order>(() => {}));

        renderPage();

        expect(screen.getByText('Cargando detalle de la orden...')).toBeInTheDocument();
    });

    it('ofrece las acciones de administrador sobre la orden recibida', async () => {
        useAuthStore.setState({
            user: { id: '1', email: 'admin@taller.cl', full_name: 'Admin', role: 'administrador', is_active: true },
            token: 't',
            isAuthenticated: true,
        });
        vi.mocked(authService.listarUsuarios).mockResolvedValue([]);
        vi.mocked(orderService.getOrderById).mockResolvedValue({
            ...orden,
            estadoCodigo: 1,
            mecanicoActualId: null,
        });
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);

        renderPage();

        expect(await screen.findByRole('button', { name: 'Asignar mecánico' })).toBeInTheDocument();
        // La cancelación se confirma desde la bandeja de cancelaciones.
        expect(screen.queryByRole('button', { name: 'Confirmar cancelación' })).not.toBeInTheDocument();
    });

    it('confirma disponibilidad desde Esperando repuestos y refresca orden e historial', async () => {
        const esperandoRepuestos = { ...orden, estadoCodigo: 4 };
        vi.mocked(orderService.getOrderById)
            .mockResolvedValueOnce(esperandoRepuestos)
            .mockResolvedValueOnce({ ...esperandoRepuestos, estadoCodigo: 5 });
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);
        vi.mocked(inventarioService.confirmarDisponibilidad).mockResolvedValue({
            claveOperacion: 'orden-101-v2', ordenId: 101, versionPresupuesto: 2,
            repuestos: [{ repuestoId: 12, cantidad: 2 }], aplicacionConfirmada: true,
        });

        renderPage();

        fireEvent.click(await screen.findByRole('button', { name: 'Confirmar disponibilidad y pasar a reparación' }));

        expect(await screen.findByText('Disponibilidad confirmada y orden en reparación.')).toBeInTheDocument();
        expect(inventarioService.confirmarDisponibilidad).toHaveBeenCalledWith(101);
        expect(orderService.getOrderById).toHaveBeenCalledTimes(2);
        expect(orderService.getOrderHistory).toHaveBeenCalledTimes(2);
        expect(screen.queryByRole('button', { name: 'Confirmar disponibilidad y pasar a reparación' })).not.toBeInTheDocument();
    });

    it('explica qué repuestos faltan ante un 409 de disponibilidad', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue({ ...orden, estadoCodigo: 4 });
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);
        vi.mocked(inventarioService.getDisponibilidadOrden).mockResolvedValue({
            ordenId: 101, disponible: false, presupuestoId: 501, version: 2,
            repuestos: [{
                repuestoId: 12, nombre: 'Pastillas', proveedorNombre: 'Proveedor', requerido: 2,
                stock: 1, reservadoParaOrden: 0, comprometidoOtrasOrdenes: 0, disponible: 1,
                alcanza: false, faltan: 1,
            }],
        });
        vi.mocked(inventarioService.confirmarDisponibilidad).mockRejectedValue({
            response: {
                status: 409,
                data: { detail: { mensaje: 'Stock insuficiente', faltantes: [{ repuesto_id: 12, requerido: 2, disponible: 1 }] } },
            },
        });

        renderPage();
        fireEvent.click(await screen.findByRole('button', { name: 'Confirmar disponibilidad y pasar a reparación' }));

        expect(await screen.findByText('Stock insuficiente: Pastillas (faltan 1)')).toBeInTheDocument();
        expect(orderService.getOrderById).toHaveBeenCalledTimes(1);
    });

    it('reconcilia una respuesta 503 cuando la orden sí avanzó a reparación', async () => {
        const esperandoRepuestos = { ...orden, estadoCodigo: 4 };
        vi.mocked(orderService.getOrderById)
            .mockResolvedValueOnce(esperandoRepuestos)
            .mockResolvedValueOnce({ ...esperandoRepuestos, estadoCodigo: 5 });
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);
        vi.mocked(inventarioService.confirmarDisponibilidad).mockRejectedValue({
            response: { status: 503, data: { detail: { mensaje: 'Aplicación pendiente' } } },
        });

        renderPage();
        fireEvent.click(await screen.findByRole('button', { name: 'Confirmar disponibilidad y pasar a reparación' }));

        expect(await screen.findByText('La confirmación se aplicó y la orden ya está en reparación.')).toBeInTheDocument();
        expect(screen.queryByText(/reintentar es seguro/)).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Confirmar disponibilidad y pasar a reparación' })).not.toBeInTheDocument();
    });

    it('conserva la reserva habitual para órdenes fuera de Esperando repuestos', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue({ ...orden, estadoCodigo: 5 });
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(hist101);
        vi.mocked(inventarioService.reservar).mockResolvedValue({ ordenId: 101, reservado: true, faltantes: [], movimientos: [] });

        renderPage();
        fireEvent.click(await screen.findByRole('button', { name: 'Reservar stock' }));

        expect(await screen.findByText('Stock reservado correctamente.')).toBeInTheDocument();
        expect(inventarioService.reservar).toHaveBeenCalledWith(101);
        expect(inventarioService.confirmarDisponibilidad).not.toHaveBeenCalled();
    });
});

describe('AdminOrderDetailPage: devolución del vehículo restaurada desde el GET', () => {
    const cancelada: Order = {
        ...orden,
        estadoCodigo: 8,
        mecanicoActualId: null,
        mecanicoNombre: undefined,
        devueltoEn: null,
        devueltoPorId: null,
    };
    const admin = {
        id: '3', email: 'admin@taller.cl', full_name: 'Admin', role: 'administrador' as const,
        roles: ['administrador' as const], is_active: true,
    };

    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useOrderHistoryStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
        useAuthStore.setState({ user: admin, token: 't', isAuthenticated: true });
        useEvidenceStore.getState().reset();
        vi.clearAllMocks();
        vi.mocked(evidenciaService.getByOrder).mockResolvedValue([]);
        vi.mocked(orderService.getOrderHistory).mockResolvedValue([]);
        vi.mocked(inventarioService.getDisponibilidadOrden).mockResolvedValue({
            ordenId: 101, disponible: true, repuestos: [], presupuestoId: 501, version: 1,
        });
    });

    it('tras recargar, una devolución ya registrada se muestra sin ofrecer otra', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue({
            ...cancelada,
            devueltoEn: '2026-11-08T13:00:00-03:00',
            devueltoPorId: '7',
        });

        renderPage();

        expect(await screen.findByText(/Vehículo devuelto el/)).toHaveTextContent('usuario n° 7');
        expect(screen.getByText(/· usuario n° 7$/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Registrar devolución' })).not.toBeInTheDocument();
        expect(orderService.getOrderById).toHaveBeenCalledWith('101');
    });

    it('una orden Cancelada sin devolución ofrece registrarla y actualiza el detalle', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue(cancelada);
        vi.mocked(orderService.registrarDevolucion).mockResolvedValue({
            ...cancelada,
            devueltoEn: '2026-11-08T13:00:00-03:00',
            devueltoPorId: '3',
        });

        renderPage();

        expect(await screen.findByText('Pendiente')).toBeInTheDocument();
        fireEvent.click(await screen.findByRole('button', { name: 'Registrar devolución' }));
        const dialogo = await screen.findByRole('dialog');
        fireEvent.click(within(dialogo).getByRole('button', { name: 'Registrar devolución' }));

        expect(await screen.findByText(/· usuario n° 3$/)).toBeInTheDocument();
        expect(screen.queryByText('Pendiente')).not.toBeInTheDocument();
        expect(screen.getAllByText('Cancelado').length).toBeGreaterThan(0);
    });
});

