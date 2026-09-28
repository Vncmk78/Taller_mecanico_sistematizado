import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OrderStateStepper } from './OrderStateStepper';

describe('OrderStateStepper: ciclo de estados de la orden', () => {
    it('muestra las 8 etapas del catálogo fijo', () => {
        render(<OrderStateStepper estadoCodigo={5} />);

        expect(screen.getByText('Ciclo de estados de la orden')).toBeInTheDocument();
        expect(screen.getByRole('list', { name: 'Ciclo de estados de la orden' })).toBeInTheDocument();
        expect(screen.getAllByRole('listitem')).toHaveLength(8);
    });

    it('marca la etapa actual con aria-current y su etiqueta', () => {
        render(<OrderStateStepper estadoCodigo={5} />);

        const current = screen.getByRole('listitem', { current: 'step' });
        expect(current).toHaveTextContent('En reparación');
        expect(current).toHaveAttribute('aria-label', 'Estado 5: En reparación');
    });

    it('no marca como actual una etapa pasada', () => {
        render(<OrderStateStepper estadoCodigo={3} />);

        expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent(
            'Esperando aprobación de presupuesto'
        );
        expect(screen.getByLabelText('Estado 1: Recibido')).not.toHaveAttribute('aria-current');
    });
});