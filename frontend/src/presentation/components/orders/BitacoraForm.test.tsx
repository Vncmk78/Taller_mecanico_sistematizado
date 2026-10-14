import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { BitacoraEntry } from '@/domain/entities/Bitacora';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderBitacoraStore } from '@/infrastructure/stores/useOrderBitacoraStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { BitacoraForm } from './BitacoraForm';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: { registrarBitacora: vi.fn() },
}));

const respuesta: BitacoraEntry = {
    id: '77',
    ordenId: '101',
    autorUsuarioId: '50',
    tipo: 'accion',
    descripcion: 'Se reemplazaron las pastillas delanteras',
    creadoEn: '2026-09-28T12:15:00-03:00',
    repuestos: [{ nombre: 'Pastillas de freno', cantidad: 2 }],
};

function renderForm() {
    return render(
        <ToastProvider>
            <BitacoraForm ordenId="101" />
        </ToastProvider>
    );
}

beforeEach(() => {
    useOrderBitacoraStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
    useOrderStore.setState({ isOffline: false });
    vi.clearAllMocks();
});

describe('BitacoraForm', () => {
    it('registra una acción sin repuestos', async () => {
        vi.mocked(orderService.registrarBitacora).mockResolvedValue({ ...respuesta, repuestos: [] });

        renderForm();

        fireEvent.change(screen.getByLabelText('Descripción de la entrada'), {
            target: { value: 'Cambio de aceite completo' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar entrada' }));

        await waitFor(() =>
            expect(orderService.registrarBitacora).toHaveBeenCalledWith('101', {
                tipo: 'accion',
                descripcion: 'Cambio de aceite completo',
                repuestos: [],
            })
        );
    });

    it('no envía si la descripción está vacía', async () => {
        renderForm();

        fireEvent.click(screen.getByRole('button', { name: 'Registrar entrada' }));

        expect(await screen.findByText('Describe la observación o la acción realizada')).toBeInTheDocument();
        expect(orderService.registrarBitacora).not.toHaveBeenCalled();
    });

    it('registra una acción con sus repuestos', async () => {
        vi.mocked(orderService.registrarBitacora).mockResolvedValue(respuesta);

        renderForm();

        fireEvent.change(screen.getByLabelText('Descripción de la entrada'), {
            target: { value: 'Se reemplazaron las pastillas delanteras' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Agregar repuesto' }));
        fireEvent.change(screen.getByLabelText('Nombre del repuesto 1'), {
            target: { value: 'Pastillas de freno' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar entrada' }));

        await waitFor(() =>
            expect(orderService.registrarBitacora).toHaveBeenCalledWith('101', {
                tipo: 'accion',
                descripcion: 'Se reemplazaron las pastillas delanteras',
                repuestos: [{ nombre: 'Pastillas de freno', cantidad: 1 }],
            })
        );
        expect(useOrderBitacoraStore.getState().entries.some((e) => e.id === '77')).toBe(true);
    });

    it('al elegir Observación oculta y limpia los repuestos', () => {
        renderForm();

        fireEvent.click(screen.getByRole('button', { name: 'Agregar repuesto' }));
        expect(screen.getByLabelText('Nombre del repuesto 1')).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText('Tipo de entrada'), { target: { value: 'observacion' } });

        expect(screen.queryByLabelText('Nombre del repuesto 1')).not.toBeInTheDocument();
    });

    it('bloquea el envío y avisa cuando no hay conexión', () => {
        useOrderStore.setState({ isOffline: true });

        renderForm();

        expect(screen.getByRole('button', { name: 'Registrar entrada' })).toBeDisabled();
        expect(
            screen.getByText('Sin conexión. No se puede registrar una entrada hasta recuperar la conexión.')
        ).toBeInTheDocument();
    });

    it('muestra el error del servidor al fallar el registro', async () => {
        vi.mocked(orderService.registrarBitacora).mockRejectedValue({
            isAxiosError: true,
            response: { status: 422, data: { detail: 'Solo una acción puede registrar repuestos utilizados' } },
        });

        renderForm();

        fireEvent.change(screen.getByLabelText('Descripción de la entrada'), {
            target: { value: 'Entrada inválida' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar entrada' }));

        expect(
            await screen.findByText('Solo una acción puede registrar repuestos utilizados')
        ).toBeInTheDocument();
    });
});
