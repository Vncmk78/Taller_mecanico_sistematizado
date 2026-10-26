import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { OrderListToolbar } from './OrderListToolbar';

function setup() {
    const onSearchChange = vi.fn();
    const onEstadoChange = vi.fn();
    render(
        <OrderListToolbar
            search=""
            onSearchChange={onSearchChange}
            estadoCodigo="all"
            onEstadoChange={onEstadoChange}
        />
    );
    return { onSearchChange, onEstadoChange };
}

describe('OrderListToolbar: búsqueda accesible', () => {
    it('expone la barra como región de búsqueda y el campo como searchbox', () => {
        setup();

        expect(
            screen.getByRole('search', { name: 'Buscar y filtrar órdenes' })
        ).toBeInTheDocument();

        const input = screen.getByRole('searchbox', { name: 'Buscar órdenes' });
        expect(input).toHaveAttribute('name', 'buscar-ordenes');
        expect(input).toHaveAttribute('autocomplete', 'off');
    });

    it('informa los cambios de búsqueda y de estado', () => {
        const { onSearchChange, onEstadoChange } = setup();

        fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar órdenes' }), {
            target: { value: 'ABCD' },
        });
        expect(onSearchChange).toHaveBeenCalledWith('ABCD');

        fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar por estado' }), {
            target: { value: '6' },
        });
        expect(onEstadoChange).toHaveBeenCalledWith(6);
    });
});
