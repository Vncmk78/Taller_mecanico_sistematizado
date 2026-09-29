import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { OrderPagination } from './OrderPagination';

const base = {
    pageSize: 6,
    onPageSizeChange: vi.fn(),
};

describe('OrderPagination: paginación del listado de órdenes', () => {
    it('se oculta cuando todo cabe en una sola página', () => {
        render(
            <OrderPagination
                page={1}
                pageCount={1}
                onPageChange={vi.fn()}
                rangeStart={1}
                rangeEnd={6}
                total={6}
                {...base}
            />
        );
        expect(screen.queryByRole('navigation', { name: 'Paginación de órdenes' })).not.toBeInTheDocument();
        expect(screen.queryByText('Mostrando 1–6 de 6 órdenes')).not.toBeInTheDocument();
    });

    it('muestra el rango y navega con Siguiente y el botón de página', () => {
        const onPageChange = vi.fn();
        render(
            <OrderPagination
                page={1}
                pageCount={3}
                onPageChange={onPageChange}
                rangeStart={1}
                rangeEnd={6}
                total={18}
                {...base}
            />
        );
        expect(screen.getByText('Mostrando 1–6 de 18 órdenes')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
        expect(onPageChange).toHaveBeenCalledWith(2);

        fireEvent.click(screen.getByRole('button', { name: 'Página 3' }));
        expect(onPageChange).toHaveBeenCalledWith(3);
    });

    it('deshabilita Anterior en la primera página y Siguiente en la última', () => {
        render(
            <OrderPagination
                page={3}
                pageCount={3}
                onPageChange={vi.fn()}
                rangeStart={13}
                rangeEnd={18}
                total={18}
                {...base}
            />
        );
        expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Anterior' })).not.toBeDisabled();
        expect(screen.getByRole('button', { name: 'Página 3' })).toHaveAttribute('aria-current', 'page');
    });
});