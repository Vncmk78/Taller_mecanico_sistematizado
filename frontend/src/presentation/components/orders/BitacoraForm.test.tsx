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

    it('asocia el error de la descripción con el campo y lo marca obligatorio', async () => {
        renderForm();

        const descripcion = screen.getByLabelText('Descripción de la entrada');
        expect(descripcion).toHaveAttribute('aria-required', 'true');
        expect(descripcion).not.toHaveAttribute('aria-invalid');

        fireEvent.click(screen.getByRole('button', { name: 'Registrar entrada' }));

        await screen.findByText('Describe la observación o la acción realizada');
        expect(descripcion).toHaveAttribute('aria-invalid', 'true');

        const errorId = descripcion.getAttribute('aria-describedby');
        expect(errorId).toBe('bitacora-descripcion-error');
        expect(document.getElementById(errorId as string)).toHaveTextContent(
            'Describe la observación o la acción realizada'
        );
    });

    it('asocia los errores de cada repuesto con su campo', async () => {
        renderForm();

        fireEvent.change(screen.getByLabelText('Descripción de la entrada'), {
            target: { value: 'Cambio de pastillas' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Agregar repuesto' }));

        const nombre = screen.getByLabelText('Nombre del repuesto 1');
        const cantidad = screen.getByLabelText('Cantidad del repuesto 1');
        expect(nombre).toHaveAttribute('aria-required', 'true');
        expect(cantidad).toHaveAttribute('aria-required', 'true');

        fireEvent.click(screen.getByRole('button', { name: 'Registrar entrada' }));
        await screen.findByText('Indica el nombre del repuesto');

        expect(nombre).toHaveAttribute('aria-invalid', 'true');
        expect(nombre.getAttribute('aria-describedby')).toBe(
            'bitacora-repuesto-0-nombre-error'
        );
        expect(document.getElementById('bitacora-repuesto-0-nombre-error')).toHaveTextContent(
            'Indica el nombre del repuesto'
        );

        fireEvent.change(nombre, { target: { value: 'Pastillas' } });
        fireEvent.change(cantidad, { target: { value: '0' } });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar entrada' }));
        await screen.findByText('La cantidad debe ser mayor que 0');

        expect(cantidad).toHaveAttribute('aria-invalid', 'true');
        expect(cantidad.getAttribute('aria-describedby')).toBe(
            'bitacora-repuesto-0-cantidad-error'
        );
        expect(document.getElementById('bitacora-repuesto-0-cantidad-error')).toHaveTextContent(
            'La cantidad debe ser mayor que 0'
        );
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
