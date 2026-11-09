import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { CapacidadMecanicos, CupoDiarioIngresos } from '@/domain/entities/ConfiguracionTaller';
import { authService } from '@/infrastructure/api/AuthService';
import { configuracionTallerService } from '@/infrastructure/api/ConfiguracionTallerService';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { formatJornada } from '@/presentation/utils/fechaJornada';
import { AdminConfigurationPage } from './AdminConfigurationPage';

vi.mock('@/infrastructure/api/AuthService', () => ({ authService: { listarUsuarios: vi.fn() } }));
vi.mock('@/infrastructure/api/ConfiguracionTallerService', () => ({
    configuracionTallerService: {
        obtenerCupoDiario: vi.fn(),
        configurarCupoDiario: vi.fn(),
        obtenerCapacidadMecanicos: vi.fn(),
        configurarCapacidadMecanicos: vi.fn(),
    },
}));

const cupo = (over: Partial<CupoDiarioIngresos> = {}): CupoDiarioIngresos => ({
    maxIngresosDiarios: 10,
    actualizadoPorId: '1',
    actualizadoEn: '2026-11-07T09:00:00-03:00',
    jornadaLocal: '2026-11-07',
    ingresosRegistrados: 4,
    sobreLimite: false,
    ...over,
});

const capacidad = (over: Partial<CapacidadMecanicos> = {}): CapacidadMecanicos => ({
    maxOrdenesActivas: 3,
    actualizadoPorId: '1',
    actualizadoEn: '2026-11-07T09:00:00-03:00',
    mecanicosSobreLimite: [],
    ...over,
});

function renderPage() {
    return render(
        <MemoryRouter>
            <ToastProvider>
                <AdminConfigurationPage />
            </ToastProvider>
        </MemoryRouter>
    );
}

const tarjeta = (nombre: string) => screen.getByRole('region', { name: nombre });

beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(authService.listarUsuarios).mockResolvedValue([
        { id: '1', email: 'a@t.cl', full_name: 'Ana Admin', roles: ['administrador'], is_active: true },
        { id: '50', email: 'm@t.cl', full_name: 'Mario Mecánico', roles: ['mecanico'], is_active: true },
    ]);
    vi.mocked(configuracionTallerService.obtenerCupoDiario).mockResolvedValue(cupo());
    vi.mocked(configuracionTallerService.obtenerCapacidadMecanicos).mockResolvedValue(capacidad());
});

describe('AdminConfigurationPage: límites independientes del taller', () => {
    it('muestra ambos límites, el uso de hoy y quién los modificó', async () => {
        renderPage();

        const ingresos = await screen.findByRole('region', { name: 'Ingresos físicos por jornada' });
        expect(await within(ingresos).findByText('10')).toBeInTheDocument();
        expect(within(ingresos).getByText('4')).toBeInTheDocument();
        expect(within(ingresos).getByText(/Ingresos del/)).toHaveTextContent(formatJornada('2026-11-07'));
        expect(await within(ingresos).findByText(/Última modificación: Ana Admin/)).toBeInTheDocument();
        expect(within(tarjeta('Órdenes activas por mecánico')).getByText('3')).toBeInTheDocument();
    });

    it('la jornada se muestra como fecha local, sin correrse al día anterior', () => {
        expect(formatJornada('2026-11-07')).toBe(new Date(2026, 10, 7).toLocaleDateString('es-CL', {
            day: '2-digit', month: 'short', year: 'numeric',
        }));
    });

    it('guarda el cupo diario y refleja el valor devuelto por MS2', async () => {
        vi.mocked(configuracionTallerService.configurarCupoDiario).mockResolvedValue(cupo({ maxIngresosDiarios: 2 }));
        renderPage();

        const ingresos = await screen.findByRole('region', { name: 'Ingresos físicos por jornada' });
        const campo = await within(ingresos).findByLabelText('Nuevo máximo de ingresos por jornada');
        fireEvent.change(campo, { target: { value: '2' } });
        fireEvent.click(within(ingresos).getByRole('button', { name: 'Guardar' }));

        expect(await screen.findByText('Máximo diario de ingresos actualizado a 2.')).toBeInTheDocument();
        expect(configuracionTallerService.configurarCupoDiario).toHaveBeenCalledWith(2);
        expect(configuracionTallerService.configurarCapacidadMecanicos).not.toHaveBeenCalled();
    });

    it.each(['0', '-1', '2.5', ''])('rechaza "%s" sin llamar a la API', async (valor) => {
        renderPage();

        const capacidadTarjeta = await screen.findByRole('region', { name: 'Órdenes activas por mecánico' });
        const campo = await within(capacidadTarjeta).findByLabelText('Nuevo máximo de órdenes activas por mecánico');
        fireEvent.change(campo, { target: { value: valor } });
        fireEvent.click(within(capacidadTarjeta).getByRole('button', { name: 'Guardar' }));

        expect(await within(capacidadTarjeta).findByText('Ingrese un número entero mayor que 0.')).toBeInTheDocument();
        expect(configuracionTallerService.configurarCapacidadMecanicos).not.toHaveBeenCalled();
    });

    it('traduce el 422 de MS2 y conserva el valor vigente', async () => {
        const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
        vi.mocked(configuracionTallerService.configurarCapacidadMecanicos).mockRejectedValue(
            new AxiosError('422', '422', config, undefined, {
                status: 422, statusText: '', headers: {}, config,
                data: { detail: [{ loc: ['body', 'max_ordenes_activas'], msg: 'Input should be greater than 0' }] },
            })
        );
        renderPage();

        const capacidadTarjeta = await screen.findByRole('region', { name: 'Órdenes activas por mecánico' });
        fireEvent.change(await within(capacidadTarjeta).findByLabelText(/Nuevo máximo/), { target: { value: '5' } });
        fireEvent.click(within(capacidadTarjeta).getByRole('button', { name: 'Guardar' }));

        expect(await within(capacidadTarjeta).findByText('El máximo debe ser un número entero positivo.')).toBeInTheDocument();
        expect(within(capacidadTarjeta).getByText('3')).toBeInTheDocument();
    });

    it('al reducir por debajo del uso avisa, sin cancelar ni desasignar', async () => {
        vi.mocked(configuracionTallerService.configurarCapacidadMecanicos).mockResolvedValue(
            capacidad({ maxOrdenesActivas: 1, mecanicosSobreLimite: [{ mecanicoId: '50', ordenesActivas: 2 }] })
        );
        vi.mocked(configuracionTallerService.configurarCupoDiario).mockResolvedValue(
            cupo({ maxIngresosDiarios: 2, sobreLimite: true })
        );
        renderPage();

        const capacidadTarjeta = await screen.findByRole('region', { name: 'Órdenes activas por mecánico' });
        fireEvent.change(await within(capacidadTarjeta).findByLabelText(/Nuevo máximo/), { target: { value: '1' } });
        fireEvent.click(within(capacidadTarjeta).getByRole('button', { name: 'Guardar' }));
        expect(await within(capacidadTarjeta).findByText('Mario Mecánico: 2 órdenes activas')).toBeInTheDocument();
        expect(within(capacidadTarjeta).getByText(/Sus órdenes se conservan/)).toBeInTheDocument();

        const ingresos = tarjeta('Ingresos físicos por jornada');
        fireEvent.change(within(ingresos).getByLabelText(/Nuevo máximo/), { target: { value: '2' } });
        fireEvent.click(within(ingresos).getByRole('button', { name: 'Guardar' }));
        expect(await within(ingresos).findByText(/ya superan el máximo. Lo registrado se conserva/)).toBeInTheDocument();
    });

    it('avisa cuando un límite aún no está configurado', async () => {
        vi.mocked(configuracionTallerService.obtenerCupoDiario).mockResolvedValue(
            cupo({ maxIngresosDiarios: null, actualizadoPorId: null })
        );
        renderPage();

        expect(await screen.findByText(/no se pueden registrar ingresos ni crear órdenes/)).toBeInTheDocument();
        expect(screen.getAllByText('Sin configurar')).toHaveLength(1);
    });

    it.each(['0', '-1', '2.5', ''])('rechaza el cupo diario "%s" sin llamar a la API', async (valor) => {
        renderPage();

        const ingresos = await screen.findByRole('region', { name: 'Ingresos físicos por jornada' });
        const campo = await within(ingresos).findByLabelText('Nuevo máximo de ingresos por jornada');
        fireEvent.change(campo, { target: { value: valor } });
        fireEvent.click(within(ingresos).getByRole('button', { name: 'Guardar' }));

        expect(await within(ingresos).findByText('Ingrese un número entero mayor que 0.')).toBeInTheDocument();
        expect(configuracionTallerService.configurarCupoDiario).not.toHaveBeenCalled();
    });

    it('acepta el valor límite 1 en cualquiera de los dos límites', async () => {
        vi.mocked(configuracionTallerService.configurarCupoDiario).mockResolvedValue(
            cupo({ maxIngresosDiarios: 1, sobreLimite: true })
        );
        vi.mocked(configuracionTallerService.configurarCapacidadMecanicos).mockResolvedValue(
            capacidad({ maxOrdenesActivas: 1 })
        );
        renderPage();

        const ingresos = await screen.findByRole('region', { name: 'Ingresos físicos por jornada' });
        fireEvent.change(within(ingresos).getByLabelText(/Nuevo máximo/), { target: { value: '1' } });
        fireEvent.click(within(ingresos).getByRole('button', { name: 'Guardar' }));

        await waitFor(() =>
            expect(configuracionTallerService.configurarCupoDiario).toHaveBeenCalledWith(1)
        );

        const capacidadTarjeta = tarjeta('Órdenes activas por mecánico');
        fireEvent.change(within(capacidadTarjeta).getByLabelText(/Nuevo máximo/), { target: { value: '1' } });
        fireEvent.click(within(capacidadTarjeta).getByRole('button', { name: 'Guardar' }));

        await waitFor(() =>
            expect(configuracionTallerService.configurarCapacidadMecanicos).toHaveBeenCalledWith(1)
        );
    });

    it('un error de consulta se puede reintentar sin afectar al otro límite', async () => {
        vi.mocked(configuracionTallerService.obtenerCupoDiario)
            .mockRejectedValueOnce(new Error('fallo'))
            .mockResolvedValueOnce(cupo());
        renderPage();

        expect(await screen.findByText('No se pudo consultar el cupo')).toBeInTheDocument();
        expect(await within(tarjeta('Órdenes activas por mecánico')).findByText('3')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /Reintentar/ }));
        expect(await within(tarjeta('Ingresos físicos por jornada')).findByText('10')).toBeInTheDocument();
    });
});
