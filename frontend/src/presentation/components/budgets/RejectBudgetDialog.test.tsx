import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { RejectBudgetDialog } from './RejectBudgetDialog';

interface SetupOverrides {
    cancelaServicio?: boolean;
    isLoading?: boolean;
    error?: string | null;
}

function setup(overrides: SetupOverrides = {}) {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
        <RejectBudgetDialog
            cancelaServicio
            onConfirm={onConfirm}
            onCancel={onCancel}
            {...overrides}
        />
    );
    return { onConfirm, onCancel };
}

describe('RejectBudgetDialog: rechazo accesible', () => {
    it('asocia el diálogo con su título y su descripción', () => {
        setup();

        const dialog = screen.getByRole('dialog', { name: 'Rechazar presupuesto' });
        const titleId = dialog.getAttribute('aria-labelledby');
        const descriptionId = dialog.getAttribute('aria-describedby');

        expect(document.getElementById(titleId as string)).toHaveTextContent('Rechazar presupuesto');
        expect(document.getElementById(descriptionId as string)).toHaveTextContent(
            /por qué rechaza este presupuesto/
        );
    });

    it('marca el motivo como obligatorio y lo describe con la ayuda y el contador', () => {
        setup();

        const motivo = screen.getByLabelText('Motivo del rechazo');
        expect(motivo).toHaveAttribute('aria-required', 'true');
        expect(motivo).not.toHaveAttribute('aria-invalid');

        const describedBy = motivo.getAttribute('aria-describedby') ?? '';
        expect(describedBy).toContain('motivo-rechazo-hint');
        expect(describedBy).toContain('motivo-rechazo-contador');
        expect(document.getElementById('motivo-rechazo-hint')).toHaveTextContent(
            'Mínimo 5 caracteres.'
        );
        expect(document.getElementById('motivo-rechazo-contador')).toHaveTextContent('0/1000');
    });

    it('asocia el error del motivo con el campo y lo anuncia', () => {
        setup();

        fireEvent.click(screen.getByRole('button', { name: 'Rechazar presupuesto' }));

        expect(screen.getByRole('alert')).toHaveTextContent('Indique el motivo del rechazo.');

        const motivo = screen.getByLabelText('Motivo del rechazo');
        expect(motivo).toHaveAttribute('aria-invalid', 'true');
        expect(motivo.getAttribute('aria-describedby')).toContain('motivo-rechazo-error');
        expect(document.getElementById('motivo-rechazo-error')).toHaveTextContent(
            'Indique el motivo del rechazo.'
        );
    });

    it('exige confirmar la cancelación del servicio antes de rechazar', () => {
        const { onConfirm } = setup();

        fireEvent.change(screen.getByLabelText('Motivo del rechazo'), {
            target: { value: 'El costo es alto' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Rechazar presupuesto' }));

        expect(screen.getByRole('alert')).toHaveTextContent(
            'Debe confirmar que desea cancelar el servicio.'
        );

        const motivo = screen.getByLabelText('Motivo del rechazo');
        const casilla = screen.getByLabelText(/Entiendo que/);
        expect(motivo).not.toHaveAttribute('aria-invalid');
        expect(casilla).toHaveAttribute('aria-invalid', 'true');
        expect(casilla).toHaveAttribute(
            'aria-describedby',
            'confirmacion-cancelacion-error'
        );
        expect(document.getElementById('confirmacion-cancelacion-error')).toHaveTextContent(
            'Debe confirmar que desea cancelar el servicio.'
        );
        expect(onConfirm).not.toHaveBeenCalled();

        fireEvent.click(casilla);
        fireEvent.click(screen.getByRole('button', { name: 'Rechazar presupuesto' }));

        expect(onConfirm).toHaveBeenCalledWith('El costo es alto', true);
    });

    it('cuando el rechazo no cancela el servicio no pide la confirmación', () => {
        const { onConfirm } = setup({ cancelaServicio: false });

        fireEvent.change(screen.getByLabelText('Motivo del rechazo'), {
            target: { value: 'El costo es alto' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Rechazar presupuesto' }));

        expect(onConfirm).toHaveBeenCalledWith('El costo es alto', false);
    });
});
