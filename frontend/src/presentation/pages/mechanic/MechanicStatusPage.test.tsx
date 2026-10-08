import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import {
    cambioEstadoBodyInvalido,
    errorAxios,
    estadoTerminalNoTransicionable,
    ordenNoEncontrada,
    sinPermisoCambiarEstado,
    transicionNoPermitida,
} from '@/infrastructure/mocks/payloads.reales';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { MechanicStatusPage } from './MechanicStatusPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        cambiarEstado: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getAssignedVehicles: vi.fn(),
    },
}));

function orden(id: string, estadoCodigo: number, mecanicoActualId: string | null = 'm1'): Order {
    return {
        id,
        vehicleId: '1',
        ingresoId: Number(id),
        estadoCodigo,
        mecanicoActualId,
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: '2026-09-05T16:30:00',
        patente: 'ABCD-12',
        vehiculo: 'Ford Fiesta',
    };
}

// Identidad real de la sesión (usuario_id de MS1).
const MECANICO_ID = 'm1';
const ordEnReparacion = orden('101', 5);
const ordDeOtro = orden('102', 1, 'm2');
// Estado 7 (Entregado): no tiene ningún avance del mecánico.
const ordEntregada = orden('103', 7);

// Fallo de transporte: error Axios sin respuesta HTTP, así que isOfflineError
// lo clasifica como "sin conexión" (no como error del servidor).
const axiosNetworkError = { isAxiosError: true };

function renderPage() {
    return render(
        <MemoryRouter>
            <ToastProvider>
                <MechanicStatusPage />
            </ToastProvider>
        </MemoryRouter>
    );
}

/** Recorre el camino completo de un avance: selector, botón y confirmación. */
async function avanzarA(ordenId: string, destino: string, observacion?: string) {
    fireEvent.change(screen.getByLabelText(`Siguiente estado de la orden ${ordenId}`), {
        target: { value: destino },
    });
    if (observacion !== undefined) {
        fireEvent.change(screen.getByLabelText(`Observación de la orden ${ordenId}`), {
            target: { value: observacion },
        });
    }
    fireEvent.click(screen.getByRole('button', { name: /Confirmar avance/ }));
    await screen.findByRole('dialog');
    fireEvent.click(screen.getByRole('button', { name: 'Avanzar estado' }));
}

describe('MechanicStatusPage: actualización de estados de las órdenes', () => {
    beforeEach(() => {
        useAuthStore.setState({
            user: {
                id: MECANICO_ID,
                email: 'mecanico@taller.cl',
                full_name: 'Mecánico Prueba',
                role: 'mecanico',
                is_active: true,
            },
        });
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
        vi.mocked(vehicleService.getAssignedVehicles).mockResolvedValue([]);
    });

    it('muestra las órdenes asignadas con los avances disponibles para el estado', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);

        renderPage();

        expect(await screen.findByText('Actualizar Estados')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getAllByText('En reparación').length).toBeGreaterThan(0);
        const selector = screen.getByLabelText('Siguiente estado de la orden 101');
        expect(selector).toBeInTheDocument();
        // "Listo" también es una opción del filtro de estado, así que se acota al selector.
        expect(within(selector).getByRole('option', { name: 'Listo' })).toBeInTheDocument();
    });

    it('pide confirmación antes de avanzar y recién entonces llama a cambiarEstado', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
        vi.mocked(orderService.cambiarEstado).mockResolvedValue({
            ...ordEnReparacion,
            estadoCodigo: 6,
        });

        renderPage();
        await screen.findByText('Orden n° 101');

        fireEvent.change(screen.getByLabelText('Siguiente estado de la orden 101'), {
            target: { value: '6' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Confirmar avance/ }));

        // El diálogo aparece y todavía no se golpeó la API.
        expect(await screen.findByRole('dialog')).toBeInTheDocument();
        expect(screen.getByText(/pasará de En reparación a Listo/)).toBeInTheDocument();
        expect(orderService.cambiarEstado).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole('button', { name: 'Avanzar estado' }));

        await waitFor(() =>
            expect(orderService.cambiarEstado).toHaveBeenCalledWith('101', 6, '')
        );
    });

    it('cancela el diálogo sin llamar a la API', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);

        renderPage();
        await screen.findByText('Orden n° 101');

        fireEvent.change(screen.getByLabelText('Siguiente estado de la orden 101'), {
            target: { value: '6' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Confirmar avance/ }));
        await screen.findByRole('dialog');
        fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));

        await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
        expect(orderService.cambiarEstado).not.toHaveBeenCalled();
    });

    it('confirma el avance, llama a cambiarEstado, actualiza la caché y avisa con un toast', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
        vi.mocked(orderService.cambiarEstado).mockResolvedValue({
            ...ordEnReparacion,
            estadoCodigo: 6,
        });

        renderPage();
        await screen.findByText('Orden n° 101');

        fireEvent.change(screen.getByLabelText('Siguiente estado de la orden 101'), {
            target: { value: '6' },
        });
        fireEvent.change(screen.getByLabelText('Observación de la orden 101'), {
            target: { value: 'Trabajo terminado' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Confirmar avance/ }));
        await screen.findByRole('dialog');
        fireEvent.click(screen.getByRole('button', { name: 'Avanzar estado' }));

        await waitFor(() =>
            expect(orderService.cambiarEstado).toHaveBeenCalledWith('101', 6, 'Trabajo terminado')
        );
        expect(await screen.findByText(/Orden n° 101 actualizada a Listo/)).toBeInTheDocument();
    });

    it('mueve a órdenes cerradas las que no tienen avance del mecánico', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion, ordEntregada]);

        renderPage();

        expect(await screen.findByText('Órdenes sin avance disponible')).toBeInTheDocument();
        expect(
            screen.getByText('No hay avances disponibles para el mecánico en este estado.')
        ).toBeInTheDocument();
        // La orden cerrada no ofrece selector de estado.
        expect(screen.queryByLabelText('Siguiente estado de la orden 103')).not.toBeInTheDocument();
        expect(screen.getByLabelText('Siguiente estado de la orden 101')).toBeInTheDocument();
    });

    it('filtra por estado desde la barra de herramientas', async () => {
        useOrderStore.setState({
            orders: [orden('101', 5), orden('102', 1)],
            status: 'success',
            error: null,
        });
        vi.mocked(orderService.getOrders).mockResolvedValue([]);

        renderPage();

        await screen.findByText('Orden n° 101');
        await screen.findByText('Orden n° 102');

        fireEvent.change(screen.getByLabelText('Filtrar por estado'), {
            target: { value: '1' },
        });

        expect(screen.queryByText('Orden n° 101')).not.toBeInTheDocument();
        expect(screen.getByText('Orden n° 102')).toBeInTheDocument();
    });

    it('muestra el detalle del error del backend (409) en la tarjeta', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
        vi.mocked(orderService.cambiarEstado).mockRejectedValue(
            errorAxios(409, transicionNoPermitida)
        );

        renderPage();
        await screen.findByText('Orden n° 101');

        await avanzarA('101', '6');

        expect(await screen.findByRole('alert')).toHaveTextContent(
            'Transición no permitida: Recibido -> En reparación'
        );
    });

    it('pagina las órdenes y respeta el tamaño de página elegido', async () => {
        // useOrderListFilters ordena por actualizadoEn descendente, así que cada
        // orden necesita su propia fecha para que la página sea determinista.
        const muchas = Array.from({ length: 8 }, (_, i) => ({
            ...orden(String(200 + i), 5),
            actualizadoEn: new Date(Date.UTC(2026, 0, 1 + i)).toISOString(),
        }));
        useOrderStore.setState({ orders: muchas, status: 'success', error: null });
        vi.mocked(orderService.getOrders).mockResolvedValue([]);

        renderPage();

        // La más reciente encabeza la lista: la 207 y la 202 llenan la primera
        // página de 6; la 201 cae en la segunda.
        expect(await screen.findByText('Orden n° 207')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 202')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 201')).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));

        expect(await screen.findByText('Orden n° 201')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 207')).not.toBeInTheDocument();
    });

    it('offline acota la caché compartida a las órdenes del mecánico', async () => {
        useOrderStore.setState({ orders: [ordEnReparacion, ordDeOtro], isOffline: true });
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
        expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 102')).not.toBeInTheDocument();
    });

    it('no muestra una orden asignada a otro mecánico aunque la caché la traiga', async () => {
        useOrderStore.setState({ orders: [ordEnReparacion, ordDeOtro], status: 'success' });
        vi.mocked(orderService.getOrders).mockResolvedValue([]);

        renderPage();

        expect(await screen.findByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 102')).not.toBeInTheDocument();
        expect(screen.queryByLabelText('Siguiente estado de la orden 102')).not.toBeInTheDocument();
    });

    // La vista no sustituye operaciones específicas. Los avances de envío y
    // stock posterior se conservan con sus precondiciones funcionales pendientes.
    describe('matriz de estados: qué ofrece el selector en cada uno', () => {
        const ESPERADOS: Record<number, string[]> = {
            1: [],
            2: ['Esperando aprobación de presupuesto'],
            3: [],
            4: ['En reparación'],
            5: ['Listo'],
            6: [],
            7: [],
            8: [],
        };

        it.each(Object.entries(ESPERADOS).map(([estado, destinos]) => [Number(estado), destinos]))(
            'en el estado %i ofrece exactamente %j',
            async (estado, destinos) => {
                useOrderStore.setState({ orders: [orden('101', estado)], status: 'success' });
                vi.mocked(orderService.getOrders).mockResolvedValue([]);

                renderPage();

                await screen.findByText('Orden n° 101');
                const selector = screen.queryByLabelText('Siguiente estado de la orden 101');
                if (destinos.length === 0) {
                    // Sin avance posible: la orden va al bloque de cerradas, sin selector.
                    expect(selector).not.toBeInTheDocument();
                    expect(
                        screen.getByText('No hay avances disponibles para el mecánico en este estado.')
                    ).toBeInTheDocument();
                    return;
                }

                expect(selector).not.toBeNull();
                const opciones = within(selector as HTMLElement)
                    .getAllByRole('option')
                    .map((o) => o.textContent);
                // La primera opción es el placeholder "Seleccionar...".
                expect(opciones.slice(1)).toEqual(destinos);
            }
        );

        it('lleva al bloque de cerradas las cuatro órdenes sin avance, en cualquier página', async () => {
            useOrderStore.setState({
                orders: [orden('301', 3), orden('302', 6), orden('303', 7), orden('304', 8)],
                status: 'success',
            });
            vi.mocked(orderService.getOrders).mockResolvedValue([]);

            renderPage();

            expect(await screen.findByText('Órdenes sin avance disponible')).toBeInTheDocument();
            for (const id of ['301', '302', '303', '304']) {
                expect(screen.getByText(`Orden n° ${id}`)).toBeInTheDocument();
                expect(screen.queryByLabelText(`Siguiente estado de la orden ${id}`)).not.toBeInTheDocument();
            }
        });
    });

    // Los tres avances conservados en AVANCES_MECANICO, y no solo el 5->6 que
    // ya cubría la suite.
    describe('avances permitidos por el mecánico', () => {
        it.each([
            [2, 3, 'Esperando aprobación de presupuesto'],
            [4, 5, 'En reparación'],
            [5, 6, 'Listo'],
        ])('avanza de %i a %i ("%s") con su observación', async (origen, destino, etiqueta) => {
            vi.mocked(orderService.getOrders).mockResolvedValue([orden('101', origen)]);
            vi.mocked(orderService.cambiarEstado).mockResolvedValue({
                ...orden('101', origen),
                estadoCodigo: destino,
            });

            renderPage();
            await screen.findByText('Orden n° 101');

            await avanzarA('101', String(destino), 'Trabajo terminado');

            await waitFor(() =>
                expect(orderService.cambiarEstado).toHaveBeenCalledWith(
                    '101',
                    destino,
                    'Trabajo terminado'
                )
            );
            expect(await screen.findByText(new RegExp(`Orden n° 101 actualizada a ${etiqueta}`))).toBeInTheDocument();
        });
    });

    describe('rechazos del backend al avanzar', () => {
        it('muestra el 403 cuando la orden ya no es del mecánico (fue reasignada)', async () => {
            vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
            vi.mocked(orderService.cambiarEstado).mockRejectedValue(
                errorAxios(403, sinPermisoCambiarEstado)
            );

            renderPage();
            await screen.findByText('Orden n° 101');

            await avanzarA('101', '6');

            // La autorización se valida antes que la transición, así que el
            // backend responde 403 y no 409 aunque el par 5->6 sea válido.
            expect(await screen.findByRole('alert')).toHaveTextContent(
                'No tienes permiso para cambiar el estado de esta orden'
            );
        });

        it('muestra el 409 de estado terminal si el servidor discrepa del estado en caché', async () => {
            vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
            vi.mocked(orderService.cambiarEstado).mockRejectedValue(
                errorAxios(409, estadoTerminalNoTransicionable)
            );

            renderPage();
            await screen.findByText('Orden n° 101');

            await avanzarA('101', '6');

            expect(await screen.findByRole('alert')).toHaveTextContent(
                'El estado Entregado es terminal y no admite transiciones'
            );
        });

        it('muestra el 404 si la orden ya no existe', async () => {
            vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
            vi.mocked(orderService.cambiarEstado).mockRejectedValue(
                errorAxios(404, ordenNoEncontrada)
            );

            renderPage();
            await screen.findByText('Orden n° 101');

            await avanzarA('101', '6');

            expect(await screen.findByRole('alert')).toHaveTextContent('Orden no encontrada');
        });

        it('traduce el 422 de FastAPI cuando el detail llega como lista', async () => {
            vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
            vi.mocked(orderService.cambiarEstado).mockRejectedValue(
                errorAxios(422, cambioEstadoBodyInvalido)
            );

            renderPage();
            await screen.findByText('Orden n° 101');

            await avanzarA('101', '6');

            expect(await screen.findByRole('alert')).toHaveTextContent(
                'Input should be greater than 0'
            );
        });

        it('deja el selector con el valor elegido para poder reintentar sin recargar', async () => {
            vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
            vi.mocked(orderService.cambiarEstado)
                .mockRejectedValueOnce(errorAxios(409, transicionNoPermitida))
                .mockResolvedValueOnce({ ...ordEnReparacion, estadoCodigo: 6 });

            renderPage();
            await screen.findByText('Orden n° 101');

            await avanzarA('101', '6', 'Reintento');

            // El fallo cierra el diálogo pero conserva la selección.
            await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
            expect(screen.getByRole('alert')).toBeInTheDocument();
            expect(screen.getByLabelText('Siguiente estado de la orden 101')).toHaveValue('6');
            expect(screen.getByLabelText('Observación de la orden 101')).toHaveValue('Reintento');

            await avanzarA('101', '6', 'Reintento');

            await waitFor(() =>
                expect(orderService.cambiarEstado).toHaveBeenCalledTimes(2)
            );
            expect(await screen.findByText(/Orden n° 101 actualizada a Listo/)).toBeInTheDocument();
            expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        });

        it('no despacha dos veces si el mecánico confirma mientras la petición sigue en vuelo', async () => {
            vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
            // Promesa pendiente: la llamada queda en vuelo durante la aserción.
            let resolver: (o: Order) => void = () => {};
            vi.mocked(orderService.cambiarEstado).mockReturnValue(
                new Promise<Order>((resolve) => {
                    resolver = resolve;
                })
            );

            renderPage();
            await screen.findByText('Orden n° 101');

            fireEvent.change(screen.getByLabelText('Siguiente estado de la orden 101'), {
                target: { value: '6' },
            });
            fireEvent.click(screen.getByRole('button', { name: /Confirmar avance/ }));
            const confirmar = await screen.findByRole('button', { name: 'Avanzar estado' });

            fireEvent.click(confirmar);

            // Con isLoading el botón cambia a "Cargando..." y queda deshabilitado,
            // así que un segundo clic no genera otra llamada.
            const enVuelo = await screen.findByRole('button', { name: /Cargando/ });
            expect(enVuelo).toBeDisabled();
            fireEvent.click(enVuelo);

            expect(orderService.cambiarEstado).toHaveBeenCalledTimes(1);

            resolver({ ...ordEnReparacion, estadoCodigo: 6 });
            expect(await screen.findByText(/Orden n° 101 actualizada a Listo/)).toBeInTheDocument();
        });
    });

    it('tras avanzar, la orden queda en Listo y pasa al bloque de cerradas', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
        vi.mocked(orderService.cambiarEstado).mockResolvedValue({
            ...ordEnReparacion,
            estadoCodigo: 6,
        });

        renderPage();
        await screen.findByText('Orden n° 101');
        expect(screen.getByLabelText('Siguiente estado de la orden 101')).toBeInTheDocument();

        await avanzarA('101', '6');

        // El 6 no tiene avance del mecánico, así que la orden sale de la lista
        // accionable: la caché se actualizó y la vista lo refleja.
        expect(await screen.findByText('Órdenes sin avance disponible')).toBeInTheDocument();
        expect(screen.queryByLabelText('Siguiente estado de la orden 101')).not.toBeInTheDocument();
        expect(screen.getAllByText('Listo').length).toBeGreaterThan(0);
    });

    it('no muestra el selector ni el botón si la sesión no tiene rol de mecánico', async () => {
        useAuthStore.setState({
            user: {
                id: MECANICO_ID,
                email: 'cliente@taller.cl',
                full_name: 'Cliente Prueba',
                role: 'cliente',
                is_active: true,
            },
        });
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);

        renderPage();

        // La orden aparece (el filtro de lista casa por id) pero sin acciones:
        // la validación por tarjeta antecede al selector y al botón.
        expect(await screen.findByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getByText('Solo el mecánico asignado puede actualizar esta orden.')).toBeInTheDocument();
        expect(screen.queryByLabelText('Siguiente estado de la orden 101')).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Confirmar avance/ })).not.toBeInTheDocument();
    });

    it('ni el rol mecánico puede actuar sobre una orden de otro mecánico', async () => {
        // La caché compartida trae una orden con asignación ajena; el filtro de
        // lista ya la descarta, y la validación por tarjeta asegura que las
        // accionables siempre tengan permiso y asignación en el render.
        vi.mocked(orderService.getOrders).mockResolvedValue([ordDeOtro]);

        renderPage();

        expect(await screen.findByText('No tiene órdenes asignadas por el momento.')).toBeInTheDocument();
        expect(screen.queryByText('Solo el mecánico asignado puede actualizar esta orden.')).not.toBeInTheDocument();
        expect(screen.queryByLabelText('Siguiente estado de la orden 102')).not.toBeInTheDocument();
    });
});
