import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import type { Order } from '@/domain/entities/Order';
import type { User, UserRole } from '@/domain/entities/User';
import { orderService } from '@/infrastructure/api/OrderService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { DevolucionVehiculoPanel } from './DevolucionVehiculoPanel';

// Simulaciones de prueba: el endpoint POST /api/ordenes/{id}/devolucion lo
// implementa el backend en paralelo (contrato-web-bloques-3-4.md, Entrega A).
vi.mock('@/infrastructure/api/OrderService', async (original) => {
    const real = await original<typeof import('@/infrastructure/api/OrderService')>();
    return {
        DevolucionSinDatosError: real.DevolucionSinDatosError,
        orderService: { registrarDevolucion: vi.fn(), getOrderById: vi.fn() },
    };
});

const FECHA = '2026-11-08T13:00:00-03:00';

function cancelada(overrides: Partial<Order> = {}): Order {
    return {
        id: '25',
        vehicleId: '9',
        ingresoId: 12,
        estadoCodigo: 8,
        mecanicoActualId: null,
        creadoPorId: '3',
        creadoEn: '2026-11-08T09:00:00-03:00',
        actualizadoEn: '2026-11-08T10:00:00-03:00',
        devueltoEn: null,
        devueltoPorId: null,
        ...overrides,
    };
}

const devuelta = (porId = '3') => cancelada({ devueltoEn: FECHA, devueltoPorId: porId, actualizadoEn: FECHA });

function sesion(roles: UserRole[]): User {
    return { id: '3', email: 'x@taller.cl', full_name: 'Usuario', role: roles[0], roles, is_active: true };
}

function iniciar(roles: UserRole[]) {
    useAuthStore.setState({ user: sesion(roles), token: 't', isAuthenticated: true });
}

const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;

function errorHttp(status: number, data: unknown): AxiosError {
    return new AxiosError(String(status), String(status), config, undefined, {
        status, statusText: String(status), data, headers: {}, config,
    });
}

const sinRespuesta = () => new AxiosError('timeout of 15000ms exceeded', 'ECONNABORTED', config);

/** Renderiza leyendo la orden desde la caché, como lo hace la página de detalle. */
function Conectado({ id }: { id: string }) {
    const order = useOrderStore((s) => s.orders.find((o) => o.id === id));
    return order ? <DevolucionVehiculoPanel order={order} /> : null;
}

function renderPanel(order: Order) {
    useOrderStore.setState({ orders: [order] });
    return render(
        <ToastProvider>
            <Conectado id={order.id} />
        </ToastProvider>
    );
}

async function confirmar() {
    fireEvent.click(screen.getByRole('button', { name: 'Registrar devolución' }));
    const dialogo = await screen.findByRole('dialog');
    fireEvent.click(within(dialogo).getByRole('button', { name: 'Registrar devolución' }));
}

beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null, isAuthenticated: false });
    useOrderStore.setState({ orders: [], isOffline: false });
});

describe('DevolucionVehiculoPanel: visibilidad', () => {
    it('ofrece la acción al Administrador en una orden Cancelada sin devolución', () => {
        iniciar(['administrador']);
        renderPanel(cancelada());

        expect(screen.getByRole('heading', { name: 'Devolución del vehículo' })).toBeInTheDocument();
        expect(screen.getByText(/aún no figura como devuelto/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Registrar devolución' })).toBeEnabled();
    });

    it('una cuenta multirrol con Administrador también la ve, aunque su primer rol sea Cliente', () => {
        iniciar(['cliente', 'administrador']);
        renderPanel(cancelada());

        expect(screen.getByRole('button', { name: 'Registrar devolución' })).toBeInTheDocument();
    });

    it.each([[['cliente']], [['mecanico']], [['cliente', 'mecanico']]] as UserRole[][][])(
        'sin rol Administrador (%j) no se muestra la sección',
        (roles) => {
            iniciar(roles);
            renderPanel(cancelada());

            expect(screen.queryByRole('heading', { name: 'Devolución del vehículo' })).not.toBeInTheDocument();
            expect(screen.queryByRole('button', { name: 'Registrar devolución' })).not.toBeInTheDocument();
        }
    );

    it.each([1, 6, 7])('no aparece en una orden en estado %i', (estadoCodigo) => {
        iniciar(['administrador']);
        renderPanel(cancelada({ estadoCodigo }));

        expect(screen.queryByRole('heading', { name: 'Devolución del vehículo' })).not.toBeInTheDocument();
    });

    it('si ya está devuelta muestra fecha y responsable del servidor y retira la acción', () => {
        iniciar(['administrador']);
        renderPanel(devuelta('7'));

        expect(screen.getByText(/Vehículo devuelto el/)).toHaveTextContent('usuario n° 7');
        expect(screen.getByText('La orden se mantiene Cancelada.')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Registrar devolución' })).not.toBeInTheDocument();
    });

    it('si la respuesta no informó la devolución, no la ofrece y permite consultar de nuevo', async () => {
        iniciar(['administrador']);
        vi.mocked(orderService.getOrderById).mockResolvedValue(cancelada());
        renderPanel(cancelada({ devueltoEn: undefined, devueltoPorId: undefined }));

        expect(screen.getByText(/no informó si el vehículo ya fue devuelto/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Registrar devolución' })).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Consultar de nuevo' }));

        expect(await screen.findByRole('button', { name: 'Registrar devolución' })).toBeInTheDocument();
        expect(orderService.getOrderById).toHaveBeenCalledWith('25');
    });
});

describe('DevolucionVehiculoPanel: registro', () => {
    it('pide confirmación explícita: cancelar el diálogo no envía nada', async () => {
        iniciar(['administrador']);
        renderPanel(cancelada());

        fireEvent.click(screen.getByRole('button', { name: 'Registrar devolución' }));
        const dialogo = await screen.findByRole('dialog');
        expect(dialogo).toHaveTextContent('La orden seguirá Cancelada');
        fireEvent.click(within(dialogo).getByRole('button', { name: 'Cancelar' }));

        await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
        expect(orderService.registrarDevolucion).not.toHaveBeenCalled();
    });

    it('al confirmar muestra la fecha y el responsable devueltos y conserva Cancelado', async () => {
        iniciar(['administrador']);
        vi.mocked(orderService.registrarDevolucion).mockResolvedValue(devuelta('3'));
        renderPanel(cancelada());

        await confirmar();

        expect(await screen.findByText(/Vehículo devuelto el/)).toHaveTextContent('usuario n° 3');
        expect(orderService.registrarDevolucion).toHaveBeenCalledWith('25');
        expect(screen.queryByRole('button', { name: 'Registrar devolución' })).not.toBeInTheDocument();
        expect(await screen.findByText('Devolución del vehículo de la orden n° 25 registrada.')).toBeInTheDocument();
        const enCache = useOrderStore.getState().orders.find((o) => o.id === '25');
        expect(enCache).toMatchObject({ estadoCodigo: 8, devueltoEn: FECHA, devueltoPorId: '3' });
    });

    it('bloquea el doble envío mientras la petición está en curso', async () => {
        iniciar(['administrador']);
        let resolver: (o: Order) => void = () => {};
        vi.mocked(orderService.registrarDevolucion).mockImplementation(
            () => new Promise<Order>((r) => { resolver = r; })
        );
        renderPanel(cancelada());

        fireEvent.click(screen.getByRole('button', { name: 'Registrar devolución' }));
        const dialogo = await screen.findByRole('dialog');
        const boton = within(dialogo).getByRole('button', { name: 'Registrar devolución' });
        fireEvent.click(boton);
        fireEvent.click(boton);
        fireEvent.keyDown(document, { key: 'Escape' });

        await waitFor(() => expect(within(dialogo).getByRole('button', { name: /Cargando/ })).toBeDisabled());
        expect(orderService.registrarDevolucion).toHaveBeenCalledTimes(1);
        expect(screen.getByRole('dialog')).toBeInTheDocument();

        resolver(devuelta());
        expect(await screen.findByText(/Vehículo devuelto el/)).toBeInTheDocument();
        expect(orderService.registrarDevolucion).toHaveBeenCalledTimes(1);
    });

    it('un 409 muestra el detail del backend sin éxito falso y deja la orden igual', async () => {
        iniciar(['administrador']);
        const detalle =
            'El ingreso del vehículo es compartido con la orden 31, que sigue activa. La entrega de esa orden cerrará el ingreso.';
        vi.mocked(orderService.registrarDevolucion).mockRejectedValue(errorHttp(409, { detail: detalle }));
        renderPanel(cancelada());

        await confirmar();

        expect(await screen.findByText(detalle)).toBeInTheDocument();
        expect(screen.queryByText(/Vehículo devuelto el/)).not.toBeInTheDocument();
        expect(screen.queryByText(/registrada\.$/)).not.toBeInTheDocument();
        expect(orderService.getOrderById).not.toHaveBeenCalled();
        expect(useOrderStore.getState().orders[0]).toMatchObject({ estadoCodigo: 8, devueltoEn: null });
        expect(screen.getByRole('button', { name: 'Registrar devolución' })).toBeEnabled();
    });

    it('un 403 también es definitivo y se muestra tal cual', async () => {
        iniciar(['administrador']);
        vi.mocked(orderService.registrarDevolucion).mockRejectedValue(
            errorHttp(403, { detail: 'Se requiere el rol Administrador' })
        );
        renderPanel(cancelada());

        await confirmar();

        expect(await screen.findByText('Se requiere el rol Administrador')).toBeInTheDocument();
        expect(orderService.getOrderById).not.toHaveBeenCalled();
    });
});

describe('DevolucionVehiculoPanel: respuesta perdida', () => {
    it('si el detalle muestra la devolución, la presenta con los datos del servidor', async () => {
        iniciar(['administrador']);
        vi.mocked(orderService.registrarDevolucion).mockRejectedValue(sinRespuesta());
        vi.mocked(orderService.getOrderById).mockResolvedValue(devuelta('3'));
        renderPanel(cancelada());

        await confirmar();

        expect(await screen.findByText(/al consultar la orden la devolución figura registrada/)).toBeInTheDocument();
        expect(screen.getByText(/Vehículo devuelto el/)).toHaveTextContent('usuario n° 3');
        expect(orderService.getOrderById).toHaveBeenCalledWith('25');
        expect(orderService.registrarDevolucion).toHaveBeenCalledTimes(1);
    });

    it('si aún no figura, avisa que podría seguir procesándose y permite comprobar de nuevo', async () => {
        iniciar(['administrador']);
        vi.mocked(orderService.registrarDevolucion).mockRejectedValue(errorHttp(504, {
            error: { codigo: 'TIEMPO_AGOTADO', mensaje: 'Tiempo agotado' },
        }));
        vi.mocked(orderService.getOrderById)
            .mockResolvedValueOnce(cancelada())
            .mockResolvedValueOnce(devuelta('3'));
        renderPanel(cancelada());

        await confirmar();

        expect(await screen.findByText(/todavía no figura registrada/)).toBeInTheDocument();
        expect(screen.queryByText(/Vehículo devuelto el/)).not.toBeInTheDocument();
        // No se reintenta la escritura automáticamente.
        expect(orderService.registrarDevolucion).toHaveBeenCalledTimes(1);

        fireEvent.click(screen.getByRole('button', { name: 'Comprobar de nuevo' }));

        expect(await screen.findByText(/Vehículo devuelto el/)).toHaveTextContent('usuario n° 3');
        expect(orderService.registrarDevolucion).toHaveBeenCalledTimes(1);
    });

    it('si tampoco se puede consultar, informa un resultado incierto', async () => {
        iniciar(['administrador']);
        vi.mocked(orderService.registrarDevolucion).mockRejectedValue(sinRespuesta());
        vi.mocked(orderService.getOrderById).mockRejectedValue(sinRespuesta());
        renderPanel(cancelada());

        await confirmar();

        expect(await screen.findByText(/Resultado incierto/)).toBeInTheDocument();
        expect(screen.queryByText(/Vehículo devuelto el/)).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Comprobar de nuevo' })).toBeInTheDocument();
    });

    it('un 200 sin fecha ni responsable se comprueba con el detalle en vez de darse por bueno', async () => {
        iniciar(['administrador']);
        const { DevolucionSinDatosError } = await import('@/infrastructure/api/OrderService');
        vi.mocked(orderService.registrarDevolucion).mockRejectedValue(new DevolucionSinDatosError());
        vi.mocked(orderService.getOrderById).mockResolvedValue(devuelta('3'));
        renderPanel(cancelada());

        await confirmar();

        expect(await screen.findByText(/Vehículo devuelto el/)).toHaveTextContent('usuario n° 3');
        expect(orderService.getOrderById).toHaveBeenCalledTimes(1);
    });
});
