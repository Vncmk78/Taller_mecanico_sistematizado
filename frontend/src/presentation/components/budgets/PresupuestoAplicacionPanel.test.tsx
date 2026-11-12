import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { PresupuestoAplicacionPanel } from './PresupuestoAplicacionPanel';

vi.mock('@/infrastructure/api/PresupuestoService', () => ({
    presupuestoService: { aplicarDecision: vi.fn(), aplicarEnvio: vi.fn(), decidir: vi.fn(), send: vi.fn() },
}));

beforeEach(() => { vi.clearAllMocks(); });

const BOTON = 'Reintentar aplicación en la orden';

it.each(['envio', 'decision'] as const)(
    'reintenta únicamente la aplicación de %s, conserva la referencia y se recupera de otro 503',
    async (tipo) => {
        const aplicar = tipo === 'envio' ? presupuestoService.aplicarEnvio : presupuestoService.aplicarDecision;
        vi.mocked(aplicar)
            .mockRejectedValueOnce({ response: { status: 503, data: { detail: 'MS2 sigue sin responder' } } })
            .mockResolvedValueOnce(undefined);
        const recargar = vi.fn().mockResolvedValue(undefined);
        render(<PresupuestoAplicacionPanel tipo={tipo} id="82" onConfirmed={recargar} />);

        expect(screen.getByText(/n° 82/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: BOTON }));
        await screen.findByRole('alert');
        expect(recargar).not.toHaveBeenCalled();
        // Sigue disponible para un reintento posterior.
        fireEvent.click(screen.getByRole('button', { name: BOTON }));
        await waitFor(() => expect(recargar).toHaveBeenCalledOnce());

        expect(aplicar).toHaveBeenCalledTimes(2);
        expect(aplicar).toHaveBeenCalledWith('82');
        expect(presupuestoService.send).not.toHaveBeenCalled();
        expect(presupuestoService.decidir).not.toHaveBeenCalled();
    }
);

it('no confirma éxito si el reintento falla', async () => {
    vi.mocked(presupuestoService.aplicarEnvio).mockRejectedValue({ response: { status: 503 } });
    const recargar = vi.fn();
    render(<PresupuestoAplicacionPanel tipo="envio" id="7" onConfirmed={recargar} />);
    fireEvent.click(screen.getByRole('button', { name: BOTON }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/sigue guardada|MS2|aplicar/i);
    expect(recargar).not.toHaveBeenCalled();
    expect(screen.getByText(/pendiente de aplicar/)).toBeInTheDocument();
});
