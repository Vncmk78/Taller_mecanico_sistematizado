import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Pagination } from './Pagination';

function setup(overrides: Partial<Parameters<typeof Pagination>[0]> = {}) {
    const onPageChange = vi.fn();
    const onPageSizeChange = vi.fn();
    const props = {
        page: 1,
        pageCount: 3,
        onPageChange,
        pageSize: 6,
        onPageSizeChange,
        rangeStart: 1,
        rangeEnd: 6,
        total: 15,
        label: 'usuarios',
        ...overrides,
    };
    const { container } = render(<Pagination {...props} />);
    return { container, onPageChange, onPageSizeChange };
}

describe('Pagination', () => {
    it('muestra el rango accesible y los tamaños 6/12/24', () => {
        setup();

        expect(screen.getByText('Mostrando 1–6 de 15 usuarios')).toBeInTheDocument();
        const selector = screen.getByRole('combobox', { name: 'Registros por página' });
        expect(
            Array.from(selector.querySelectorAll('option')).map((option) => option.value)
        ).toEqual(['6', '12', '24']);
        expect(selector).toHaveValue('6');
    });

    it('permite cambiar de página y avisa al selector de tamaño', () => {
        const { onPageChange, onPageSizeChange } = setup();

        fireEvent.click(screen.getByRole('button', { name: 'Página 2' }));
        expect(onPageChange).toHaveBeenCalledWith(2);

        fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
        expect(onPageChange).toHaveBeenCalledWith(2);

        fireEvent.change(screen.getByRole('combobox', { name: 'Registros por página' }), {
            target: { value: '12' },
        });
        expect(onPageSizeChange).toHaveBeenCalledWith(12);
    });

    it('deshabilita los extremos cuando no hay más páginas', () => {
        setup({ page: 1 });
        expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Siguiente' })).toBeEnabled();

        cleanup();
        setup({ page: 3 });
        expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Anterior' })).toBeEnabled();
    });

    it('marca la página activa para lectores de pantalla', () => {
        setup({ page: 2 });
        expect(screen.getByRole('button', { name: 'Página 2' })).toHaveAttribute(
            'aria-current',
            'page'
        );
    });

    it('usa las etiquetas accesibles personalizadas de cada listado', () => {
        setup({ ariaLabel: 'Paginación de usuarios', sizeLabel: 'Usuarios por página' });

        expect(
            screen.getByRole('navigation', { name: 'Paginación de usuarios' })
        ).toBeInTheDocument();
        expect(
            screen.getByRole('combobox', { name: 'Usuarios por página' })
        ).toBeInTheDocument();
    });

    it('no renderiza nada cuando la colección cabe en una página', () => {
        const { container } = setup({ total: 4, pageCount: 1, rangeEnd: 4 });

        expect(container).toBeEmptyDOMElement();
    });

    it('comprime los números con elipsis cuando hay más de siete páginas', () => {
        setup({ page: 5, pageCount: 12, total: 72, rangeStart: 25, rangeEnd: 30 });

        expect(screen.getByRole('button', { name: 'Página 1' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Página 5' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Página 12' })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Página 7' })).not.toBeInTheDocument();
    });
});
