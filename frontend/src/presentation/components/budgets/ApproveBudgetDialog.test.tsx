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

    it('describe la casilla de revisión y la marca como obligatoria', () => {
        setup();

        const casilla = screen.getByLabelText(/He revisado las partidas y el total/);
        expect(casilla).toHaveAttribute('aria-required', 'true');
        expect(casilla).toHaveAttribute('aria-describedby', 'aprobar-revisado-hint');
        expect(document.getElementById('aprobar-revisado-hint')).toHaveTextContent(
            'Marque la casilla para habilitar la confirmación.'
        );
    });

    it('asocia el diálogo con su título y su descripción', () => {
        setup();

        const dialog = screen.getByRole('dialog', { name: 'Aprobar presupuesto' });
        const titleId = dialog.getAttribute('aria-labelledby');
        const descriptionId = dialog.getAttribute('aria-describedby');

        expect(document.getElementById(titleId as string)).toHaveTextContent('Aprobar presupuesto');
        expect(document.getElementById(descriptionId as string)).toHaveTextContent(
            /Al aprobar, autoriza al taller/
        );
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
