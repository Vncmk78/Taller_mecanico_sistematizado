import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ApproveBudgetDialog } from './ApproveBudgetDialog';

interface SetupOverrides {
    total?: number;
    cantidadPartidas?: number;
    isLoading?: boolean;
    error?: string | null;
}

function setup(overrides: SetupOverrides = {}) {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
        <ApproveBudgetDialog
            total={108000}
            cantidadPartidas={3}
            onConfirm={onConfirm}
            onCancel={onCancel}
            {...overrides}
        />
    );
    return { onConfirm, onCancel };
}

describe('ApproveBudgetDialog: confirmación de aprobación', () => {
    it('muestra el total y bloquea la aprobación hasta aceptar la revisión', () => {
        const { onConfirm } = setup();

        expect(screen.getByRole('dialog', { name: 'Aprobar presupuesto' })).toBeInTheDocument();
        expect(screen.getByText('$108.000')).toBeInTheDocument();
        expect(screen.getByText(/3 partidas/)).toBeInTheDocument();

        const confirmar = screen.getByRole('button', { name: 'Confirmar aprobación' });
        expect(confirmar).toBeDisabled();
        fireEvent.click(confirmar);
        expect(onConfirm).not.toHaveBeenCalled();

        fireEvent.click(screen.getByLabelText(/He revisado las partidas y el total/));
        expect(confirmar).not.toBeDisabled();
        fireEvent.click(confirmar);
        expect(onConfirm).toHaveBeenCalledTimes(1);
    });

    it('singulariza la cantidad de partidas y muestra el error del servidor', () => {
        setup({ cantidadPartidas: 1, error: 'El servidor tuvo un problema.' });

        expect(screen.getByText(/1 partida\)/)).toBeInTheDocument();
        expect(screen.getByText('El servidor tuvo un problema.')).toBeInTheDocument();
    });

    it('mientras envía deshabilita cancelar y confirmar', () => {
        setup({ isLoading: true });

        expect(screen.getByRole('button', { name: /Cargando/ })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Cancelar' })).toBeDisabled();
    });

    it('cancela desde el botón secundario', () => {
        const { onCancel } = setup();

        fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));

        expect(onCancel).toHaveBeenCalledTimes(1);
    });
});
