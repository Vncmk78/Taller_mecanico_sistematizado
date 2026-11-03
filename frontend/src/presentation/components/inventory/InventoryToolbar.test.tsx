import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { InventoryToolbar } from './InventoryToolbar';

function setup(estado: 'todos' | 'sin_stock' | 'critico' | 'bajo' | 'normal' = 'todos') {
    const onSearchChange = vi.fn();
    const onEstadoChange = vi.fn();
    render(
        <InventoryToolbar
            search=""
            onSearchChange={onSearchChange}
            estado={estado}
            onEstadoChange={onEstadoChange}
        />
    );
    return { onSearchChange, onEstadoChange };
}

describe('InventoryToolbar: búsqueda y filtro accesibles', () => {
    it('expone la barra como región de búsqueda y el campo como searchbox', () => {
        setup();

        expect(
            screen.getByRole('search', { name: 'Buscar y filtrar repuestos' })
        ).toBeInTheDocument();

        const input = screen.getByRole('searchbox', { name: 'Buscar repuestos' });
        expect(input).toHaveAttribute('name', 'buscar-repuestos');
        expect(input).toHaveAttribute('autocomplete', 'off');
    });

    it('ofrece los cuatro estados de stock más la opción "todos"', () => {
        setup();

        const opciones = screen
            .getAllByRole('option')
            .map((opcion) => (opcion as HTMLOptionElement).value);

        expect(opciones).toEqual(['todos', 'sin_stock', 'critico', 'bajo', 'normal']);
    });

    it('informa los cambios de búsqueda y de estado', () => {
        const { onSearchChange, onEstadoChange } = setup();

        fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar repuestos' }), {
            target: { value: 'filtro' },
        });
        expect(onSearchChange).toHaveBeenCalledWith('filtro');

        fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar por estado de stock' }), {
            target: { value: 'critico' },
        });
        expect(onEstadoChange).toHaveBeenCalledWith('critico');
    });
});
