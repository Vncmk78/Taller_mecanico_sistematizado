import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import type { User, UsuarioListado } from '@/domain/entities/User';
import { authService } from '@/infrastructure/api/AuthService';
import { orderService } from '@/infrastructure/api/OrderService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { OrderActionsPanel } from './OrderActionsPanel';

vi.mock('@/infrastructure/api/AuthService', () => ({
    authService: { listarUsuarios: vi.fn() },
}));

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        cambiarEstado: vi.fn(),
        asignarMecanico: vi.fn(),
        registrarEntrega: vi.fn(),
        cancelarComoCliente: vi.fn(),
        confirmarCancelacion: vi.fn(),
    },
}));

const MECANICOS: UsuarioListado[] = [
    { id: '50', email: 'mecanico@taller.cl', full_name: 'Martín Herrera', roles: ['mecanico'], is_active: true },
    { id: '51', email: 'jefe@taller.cl', full_name: 'Jefe Taller', roles: ['mecanico', 'administrador'], is_active: true },
];

function sesion(rol: User['role'], id = '99'): User {
    return { id, email: `${rol}@taller.cl`, full_name: `Usuario ${rol}`, role: rol, is_active: true };
}

function orden(overrides: Partial<Order> = {}): Order {
    return {
        id: '101',
        vehicleId: '1',
        ingresoId: 1,
        estadoCodigo: 1,
        mecanicoActualId: null,
        creadoPorId: '99',
        creadoEn: '2026-09-01T10:15:00',
        actualizadoEn: '2026-09-05T16:30:00',
        patente: 'ABCD-12',
        vehiculo: 'Ford Fiesta',
        ...overrides,
    };
}

function renderPanel(order: Order) {
    return render(
        <MemoryRouter>
            <ToastProvider>
                <OrderActionsPanel order={order} />
            </ToastProvider>
        </MemoryRouter>
    );
}

beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null, isAuthenticated: false });
    useOrderStore.setState({ isOffline: false });
    vi.mocked(authService.listarUsuarios).mockResolvedValue(MECANICOS);
});

describe('OrderActionsPanel: catálogo centralizado en la interfaz', () => {
    it('el administrador ve asignar y cancelar en Recibido y carga los mecánicos', async () => {
        useAuthStore.setState({ user: sesion('administrador'), token: 't', isAuthenticated: true });

        renderPanel(orden({ estadoCodigo: 1 }));

        expect(await screen.findByRole('button', { name: 'Asignar mecánico' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Confirmar cancelación' })).toBeInTheDocument();
        expect(await screen.findByRole('option', { name: 'Martín Herrera' })).toBeInTheDocument();
        await waitFor(() => expect(authService.listarUsuarios).toHaveBeenCalledTimes(1));
    });

    it('el administrador registra la entrega física de una orden Listo', async () => {
        useAuthStore.setState({ user: sesion('administrador'), token: 't', isAuthenticated: true });
        vi.mocked(orderService.registrarEntrega).mockResolvedValue(orden({ estadoCodigo: 7 }));

        renderPanel(orden({ estadoCodigo: 6 }));

        fireEvent.click(screen.getByRole('button', { name: 'Registrar entrega' }));
        const dialog = await screen.findByRole('dialog', { name: '¿Registrar la entrega del vehículo?' });
        fireEvent.click(within(dialog).getByRole('button', { name: 'Registrar entrega' }));

        await waitFor(() => expect(orderService.registrarEntrega).toHaveBeenCalledWith('101', ''));
        expect(await screen.findByText('Orden n° 101 actualizada a Entregado.')).toBeInTheDocument();
    });

    it('el cliente en aprobación ve gestionar presupuesto y cancelar solicitud', () => {
        useAuthStore.setState({ user: sesion('cliente'), token: 't', isAuthenticated: true });

        renderPanel(orden({ estadoCodigo: 3 }));

        expect(screen.getByRole('link', { name: 'Gestionar presupuesto' })).toHaveAttribute(
            'href',
            '/client/presupuestos/101'
        );
        expect(screen.getByRole('button', { name: 'Solicitar cancelación' })).toBeInTheDocument();
    });

    it('no ofrece acciones cuando el estado no habilita ninguna para el rol', () => {
        useAuthStore.setState({ user: sesion('cliente'), token: 't', isAuthenticated: true });

        renderPanel(orden({ estadoCodigo: 5 }));

        expect(screen.queryByLabelText('Acciones de la orden')).not.toBeInTheDocument();
    });

    it('la cancelación del cliente exige motivo antes de llamar al servicio', async () => {
        useAuthStore.setState({ user: sesion('cliente'), token: 't', isAuthenticated: true });
        vi.mocked(orderService.cancelarComoCliente).mockResolvedValue(orden({ estadoCodigo: 2 }));

        renderPanel(orden({ estadoCodigo: 2 }));

        fireEvent.click(screen.getByRole('button', { name: 'Solicitar cancelación' }));
        fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Solicitar cancelación' }));

        expect(await screen.findByText('Debe indicar un motivo.')).toBeInTheDocument();
        expect(orderService.cancelarComoCliente).not.toHaveBeenCalled();

        fireEvent.change(screen.getByLabelText('Motivo de la orden 101'), {
            target: { value: 'Ya no deseo el servicio' },
        });
        fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Solicitar cancelación' }));

        await waitFor(() =>
            expect(orderService.cancelarComoCliente).toHaveBeenCalledWith('101', 'Ya no deseo el servicio')
        );
        expect(await screen.findByText(/Solicitud de cancelación.*enviada.*Pendiente de confirmación administrativa/)).toBeInTheDocument();
        expect(orderService.cambiarEstado).not.toHaveBeenCalled();
    });

    it('asocia el error del motivo de cancelación con el campo', async () => {
        useAuthStore.setState({ user: sesion('cliente'), token: 't', isAuthenticated: true });

        renderPanel(orden({ estadoCodigo: 2 }));

        fireEvent.click(screen.getByRole('button', { name: 'Solicitar cancelación' }));
        fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Solicitar cancelación' }));

        expect(await screen.findByText('Debe indicar un motivo.')).toBeInTheDocument();

        const motivo = screen.getByLabelText('Motivo de la orden 101');
        expect(motivo).toHaveAttribute('aria-required', 'true');
        expect(motivo).toHaveAttribute('aria-invalid', 'true');
        expect(motivo.getAttribute('aria-describedby')).toBe(
            'orden-101-cancelar-motivo-error'
        );
        expect(document.getElementById('orden-101-cancelar-motivo-error')).toHaveTextContent(
            'Debe indicar un motivo.'
        );
    });

    it('el mecánico no asignado ve su acción bloqueada y el asignado solo con destino', () => {
        useAuthStore.setState({ user: sesion('mecanico', '60'), token: 't', isAuthenticated: true });
        const noAsignada = renderPanel(orden({ estadoCodigo: 5, mecanicoActualId: '50' }));
        expect(screen.getByRole('button', { name: 'Avanzar estado' })).toBeDisabled();
        noAsignada.unmount();

        useAuthStore.setState({ user: sesion('mecanico', '50'), token: 't', isAuthenticated: true });
        renderPanel(orden({ estadoCodigo: 5, mecanicoActualId: '50' }));

        const boton = screen.getByRole('button', { name: 'Avanzar estado' });
        expect(boton).toBeDisabled();

        fireEvent.change(screen.getByLabelText('Siguiente estado de la orden 101'), {
            target: { value: '6' },
        });
        expect(screen.getByRole('button', { name: 'Avanzar estado' })).toBeEnabled();
    });

    it('el mecánico asignado confirma el avance recién después del diálogo', async () => {
        useAuthStore.setState({ user: sesion('mecanico', '50'), token: 't', isAuthenticated: true });
        vi.mocked(orderService.cambiarEstado).mockResolvedValue(orden({ estadoCodigo: 6 }));

        renderPanel(orden({ estadoCodigo: 5, mecanicoActualId: '50' }));

        fireEvent.change(screen.getByLabelText('Siguiente estado de la orden 101'), {
            target: { value: '6' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Avanzar estado' }));

        const dialog = await screen.findByRole('dialog', {
            name: '¿Confirmar el avance de estado?',
        });
        expect(screen.getByText(/pasará de En reparación a Listo/)).toBeInTheDocument();
        expect(orderService.cambiarEstado).not.toHaveBeenCalled();

        fireEvent.click(within(dialog).getByRole('button', { name: 'Avanzar estado' }));

        await waitFor(() => expect(orderService.cambiarEstado).toHaveBeenCalledWith('101', 6, ''));
    });

    it('el administrador asigna un mecánico recién tras confirmar en el diálogo', async () => {
        useAuthStore.setState({ user: sesion('administrador'), token: 't', isAuthenticated: true });
        vi.mocked(orderService.asignarMecanico).mockResolvedValue(
            orden({ estadoCodigo: 2, mecanicoActualId: '50' })
        );

        renderPanel(orden({ estadoCodigo: 1 }));

        const boton = screen.getByRole('button', { name: 'Asignar mecánico' });
        await screen.findByRole('option', { name: 'Martín Herrera' });
        expect(boton).toBeDisabled();

        fireEvent.change(screen.getByLabelText('Mecánico para la orden 101'), {
            target: { value: '50' },
        });
        expect(boton).toBeEnabled();
        fireEvent.click(boton);

        const dialog = await screen.findByRole('dialog', { name: '¿Confirmar la asignación?' });
        expect(screen.getByText(/quedará a cargo de Martín Herrera/)).toBeInTheDocument();
        expect(orderService.asignarMecanico).not.toHaveBeenCalled();

        fireEvent.click(within(dialog).getByRole('button', { name: 'Asignar mecánico' }));

        await waitFor(() =>
            expect(orderService.asignarMecanico).toHaveBeenCalledWith('101', '50', '')
        );
    });

    it('el administrador confirma una solicitud por su endpoint específico', async () => {
        useAuthStore.setState({ user: sesion('administrador'), token: 't', isAuthenticated: true });
        vi.mocked(orderService.confirmarCancelacion).mockResolvedValue(orden({ estadoCodigo: 8 }));
        renderPanel(orden({ estadoCodigo: 3 }));

        fireEvent.click(screen.getByRole('button', { name: 'Confirmar cancelación' }));
        const dialog = await screen.findByRole('dialog');
        expect(within(dialog).getByText(/solicitud pendiente.*MS2 comprobará/)).toBeInTheDocument();
        fireEvent.click(within(dialog).getByRole('button', { name: 'Confirmar cancelación' }));

        await waitFor(() => expect(orderService.confirmarCancelacion).toHaveBeenCalledWith('101'));
        expect(orderService.cambiarEstado).not.toHaveBeenCalled();
        expect(await screen.findByText('Orden n° 101 actualizada a Cancelado.')).toBeInTheDocument();
    });

    it('sin conexión deshabilita las acciones y avisa al usuario', () => {
        useAuthStore.setState({ user: sesion('administrador'), token: 't', isAuthenticated: true });
        useOrderStore.setState({ isOffline: true });

        renderPanel(orden({ estadoCodigo: 1 }));

        expect(screen.getByRole('button', { name: 'Asignar mecánico' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Confirmar cancelación' })).toBeDisabled();
        expect(screen.getByText(/para modificar el estado de la orden necesita estar conectado/)).toBeInTheDocument();
    });

    it('el administrador reasigna sin ofrecer al responsable actual y conserva el estado', async () => {
        useAuthStore.setState({ user: sesion('administrador'), token: 't', isAuthenticated: true });
        vi.mocked(orderService.asignarMecanico).mockResolvedValue(
            orden({ estadoCodigo: 3, mecanicoActualId: '51' })
        );

        renderPanel(orden({ estadoCodigo: 3, mecanicoActualId: '50' }));

        const boton = screen.getByRole('button', { name: 'Reasignar mecánico' });
        await screen.findByRole('option', { name: 'Jefe Taller' });
        expect(screen.queryByRole('option', { name: 'Martín Herrera' })).not.toBeInTheDocument();
        expect(screen.getByLabelText('Nuevo mecánico responsable')).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText('Mecánico para la orden 101'), {
            target: { value: '51' },
        });
        fireEvent.click(boton);

        const dialog = await screen.findByRole('dialog', { name: '¿Confirmar la reasignación?' });
        expect(screen.getByText(/pasará a Jefe Taller y conservará su estado/)).toBeInTheDocument();
        fireEvent.click(within(dialog).getByRole('button', { name: 'Reasignar mecánico' }));

        await waitFor(() =>
            expect(orderService.asignarMecanico).toHaveBeenCalledWith('101', '51', '')
        );
        expect(await screen.findByText(/reasignada. Conserva el estado/)).toBeInTheDocument();
    });

    it('muestra el rechazo por capacidad de MS2 sin cambiar la orden', async () => {
        useAuthStore.setState({ user: sesion('administrador'), token: 't', isAuthenticated: true });
        const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
        vi.mocked(orderService.asignarMecanico).mockRejectedValue(
            new AxiosError('409', '409', config, undefined, {
                status: 409, statusText: '', headers: {}, config,
                data: { detail: 'El mecánico alcanzó el máximo de órdenes activas' },
            })
        );
        const actualizar = vi.spyOn(useOrderStore.getState(), 'updateOrder');

        renderPanel(orden({ estadoCodigo: 1 }));
        await screen.findByRole('option', { name: 'Martín Herrera' });
        fireEvent.change(screen.getByLabelText('Mecánico para la orden 101'), {
            target: { value: '50' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Asignar mecánico' }));
        const dialog = await screen.findByRole('dialog');
        fireEvent.click(within(dialog).getByRole('button', { name: 'Asignar mecánico' }));

        expect(
            await screen.findByText('El mecánico alcanzó el máximo de órdenes activas')
        ).toBeInTheDocument();
        expect(actualizar).not.toHaveBeenCalled();
    });
});

it('la cuenta Cliente+Administrador ejerce administración desde su portal aunque Cliente sea primero', async () => {
    useAuthStore.setState({ user: { ...sesion('cliente'), roles: ['cliente', 'administrador'] }, token: 't', isAuthenticated: true });
    vi.mocked(authService.listarUsuarios).mockResolvedValue(MECANICOS);
    render(<MemoryRouter initialEntries={['/admin/ordenes/101']}><ToastProvider><OrderActionsPanel order={orden()} /></ToastProvider></MemoryRouter>);
    expect(await screen.findByRole('button', { name: 'Asignar mecánico' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Solicitar cancelación' })).not.toBeInTheDocument();
});
