import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { useToast } from '@/presentation/components/ui/toastContext';

function BotonDePrueba() {
    const { showToast } = useToast();
    return (
        <div>
            <button type="button" onClick={() => showToast('Orden actualizada.', 'success')}>
                Confirmar
            </button>
            <button type="button" onClick={() => showToast('No se pudo actualizar.')}>
                Fallar
            </button>
        </div>
    );
}

function renderProvider() {
    return render(
        <ToastProvider>
            <BotonDePrueba />
        </ToastProvider>
    );
}

describe('ToastProvider: avisos flotantes', () => {
    afterEach(() => {
        vi.useRealTimers();
    });

    it('no muestra avisos hasta que se solicita uno', () => {
        renderProvider();

        expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });

    it('muestra el aviso con el texto entregado', () => {
        renderProvider();

        fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }));

        expect(screen.getByRole('status')).toHaveTextContent('Orden actualizada.');
    });

    it('el tono por defecto es informativo', () => {
        renderProvider();

        fireEvent.click(screen.getByRole('button', { name: 'Fallar' }));

        expect(screen.getByRole('status')).toHaveTextContent('No se pudo actualizar.');
    });

    it('permite cerrar el aviso manualmente', () => {
        renderProvider();

        fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }));
        expect(screen.getByRole('status')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Cerrar aviso' }));

        expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });

    it('cierra el aviso con la tecla Escape', () => {
        renderProvider();

        fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }));
        fireEvent.keyDown(document, { key: 'Escape' });

        expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });

    it('acumula varios avisos a la vez', () => {
        renderProvider();

        fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }));
        fireEvent.click(screen.getByRole('button', { name: 'Fallar' }));

        expect(screen.getAllByRole('status')).toHaveLength(2);
    });

    it('cierra el aviso solo tras unos segundos', () => {
        vi.useFakeTimers();
        renderProvider();

        fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }));
        expect(screen.getByRole('status')).toBeInTheDocument();

        // Todavía no debe cerrarse antes de tiempo.
        act(() => {
            vi.advanceTimersByTime(3000);
        });
        expect(screen.getByRole('status')).toBeInTheDocument();

        act(() => {
            vi.advanceTimersByTime(1500);
        });
        expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });

    it('useToast falla fuera del provider', () => {
        expect(() => render(<BotonDePrueba />)).toThrow(
            'useToast debe usarse dentro de un ToastProvider'
        );
    });
});
